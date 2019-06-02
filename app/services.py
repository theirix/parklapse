import datetime
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile

logger = logging.getLogger(__name__)


class VideoService:

    def __init__(self, raw_capture_path, timelapse_path, tmp_path):
        self.raw_capture_path = raw_capture_path
        self.timelapse_path = timelapse_path
        self.tmp_path = tmp_path

    def _enumerate_files(self) -> list:
        return list(sorted(file for file
                           in glob.glob(self.raw_capture_path + '/*/*.mp4')
                           if os.path.isfile(file)))

    def raw_count(self):
        return len(self._enumerate_files())

    @staticmethod
    def _parse_dt(fname: str) -> datetime.datetime:
        # out-20190602T1705.mp4
        m = re.match(r'out-(.*)\.mp4', os.path.basename(fname))
        if not m:
            raise ValueError('Wrong filename')
        return datetime.datetime.strptime(m.group(1), "%Y%m%dT%H%M")

    def raw_last_at(self):
        files = self._enumerate_files()
        if len(files) < 2:
            return None
        last_completed_file = files[-2]
        return self._parse_dt(last_completed_file)

    @staticmethod
    def _timelapse_hourly_slot(dt: datetime.datetime) -> int:
        """Returns index of three-hour interval (1 to 9)"""
        return (dt.hour // 3) + 1

    def produce_timelapse(self, dt: datetime.datetime, hourly_slot: int):
        try:
            logger.info(f"Creating timelapse for date {dt.isoformat()} and slot {hourly_slot}")
            slot_files = [file for file in self._enumerate_files() if
                          self._parse_dt(file).date() == dt.date() and
                          self._timelapse_hourly_slot(self._parse_dt(file)) == hourly_slot]
            if len(slot_files) < 2:
                logger.info("Nothing to do")
                return
            slot_files.pop()
            if slot_files:
                slot_files = slot_files[0:2]
            for file in slot_files:
                logger.info(" - file " + file)

            with tempfile.TemporaryDirectory(prefix='parklapse', dir=self.tmp_path) as tmpdirname:
                in_video_path = self._compose_concat_video(tmpdirname, slot_files, hourly_slot)
                logger.info(f"Got composed video path: {in_video_path}")
                out_video_path = self._compose_timelapse_video(tmpdirname, in_video_path, dt, hourly_slot)
                logger.info(f"Got timelapse video path: {out_video_path}")
                logger.info(f"Video size: {os.stat(out_video_path).st_size // (1024 * 1024)} MiB")
                shutil.move(out_video_path, self.timelapse_path)
        except Exception as e:
            logger.error(str(e))
            logger.exception(e)
            raise

    @staticmethod
    def local_bin():
        if sys.platform.startswith('darwin'):
            return '/usr/local/bin'
        if sys.platform.startswith('linux'):
            return '/usr/bin'
        raise RuntimeError('wrong platform')

    def _compose_concat_video(self, tmpdirname: str, files: list, hourly_slot: int) -> str:
        if not files:
            raise RuntimeError('No files')
        if not hourly_slot:
            raise RuntimeError('Wrong hourly slot')

        video_path = os.path.join(tmpdirname, f"concatvideo_{hourly_slot}.mp4")
        if os.path.isfile(video_path):
            logger.warning(f'Removing existing target {video_path}')

        command = [os.path.join(self.local_bin(), 'mkvmerge')]
        for file in files:
            command.append(file)
            command.append('+')
        command.pop()
        command.extend([
            '-o',
            video_path])
        logger.info("Launching: " + " ".join(command))
        res = subprocess.run(command, shell=False, check=False,
                             stdout=None, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise RuntimeError('Concatenation failed ' + str(res.stderr.decode('latin-1')))
        logger.info("Succeed")
        return video_path

    def _compose_timelapse_video(self, tmpdirname: str, in_video_path: str, dt: datetime.datetime,
                                 hourly_slot: int) -> str:
        bitrate = 4  # mbs
        fps = 24
        speedup = 60  # times
        out_video_path = os.path.join(tmpdirname, "timelapse-{}_{}.mp4".format(dt.strftime('%Y%m%d'),
                                                                               hourly_slot))

        command = [os.path.join(self.local_bin(), 'ffmpeg')]
        command.extend(['-hide_banner',
                        '-i',
                        in_video_path])
        command_str = f"-vf setpts=PTS/{speedup} -r {fps} -c:v libx264 -preset slow " + \
                      f"-b:v {bitrate}M -maxrate {bitrate}M -bufsize {bitrate // 2}M " + \
                      f"-g {fps} -keyint_min {fps} -force_key_frames expr:gte(t,n_forced*1)"
        command.extend(command_str.split(' '))
        command.extend([
            out_video_path])
        logger.info("Launching: " + repr(command))
        res = subprocess.run(command, shell=False, check=False,
                             stdout=None, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise RuntimeError('Recode failed ' + str(res.stderr.decode('latin-1')))
        logger.info("Succeed")
        return out_video_path

    def check_timelapses(self):
        last_at = self.raw_last_at()
        now = datetime.datetime.now()
        if not last_at:
            return
        self.produce_timelapse(last_at, self._timelapse_hourly_slot(last_at))
        # if self._timelapse_hourly_slot(last_at) != self._timelapse_hourly_slot(now):
        #     logger.info("Found timelapse")
