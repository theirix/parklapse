import datetime
import glob
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)


class VideoService:

    def __init__(self, *args):
        if args:
            self.init_config(*args)

    # noinspection PyAttributeOutsideInit
    def init_config(self, raw_capture_path, timelapse_path, tmp_path):
        self.raw_capture_path = raw_capture_path
        self.timelapse_path = timelapse_path
        self.tmp_path = tmp_path
        if not self.raw_capture_path or not os.path.isdir(self.raw_capture_path):
            raise RuntimeError('Bad raw_capture_path')
        if not self.timelapse_path or not os.path.isdir(self.timelapse_path):
            raise RuntimeError('Bad timelapse_path')

    def _enumerate_files(self) -> list:
        return list(sorted(file for file
                           in glob.glob(self.raw_capture_path + '/*/*.mp4')
                           if os.path.isfile(file)))

    def raw_count(self):
        return len(self._enumerate_files())

    @staticmethod
    def _parse_raw_dt(fname: str) -> datetime.datetime:
        # out-20190602T1705.mp4
        m = re.match(r'out-(.*)\.mp4', os.path.basename(fname))
        if not m:
            raise ValueError('Wrong filename')
        return datetime.datetime.strptime(m.group(1), "%Y%m%dT%H%M")

    @staticmethod
    def _parse_timelapse_to_date_and_slot(fname: str) -> (datetime.date, int):
        # timelapse-20190602_3.mp4
        m = re.match(r'timelapse-(\d+)_(\d)\.mp4', os.path.basename(fname))
        if not m:
            raise ValueError('Wrong filename')
        dt = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        slot = int(m.group(2))
        logger.debug(f"Res: {dt!r} {slot!r}")
        return dt, slot

    def raw_last_at(self) -> Optional[datetime.datetime]:
        files = self._enumerate_files()
        if len(files) < 2:
            return None
        last_completed_file = files[-2]
        return self._parse_raw_dt(last_completed_file)

    def timelapses_error_count(self):
        return len([file for file
                    in glob.glob(self.timelapse_path + '/*.err')
                    if os.path.isfile(file)])

    def timelapses_count(self):
        return len([file for file
                    in glob.glob(self.timelapse_path + '/*.mp4')
                    if os.path.isfile(file)])

    def timelapse_last_file(self):
        files = sorted([file for file
                        in glob.glob(self.timelapse_path + '/*.mp4')
                        if os.path.isfile(file)])
        if not files:
            return None
        return os.path.basename(files[-1])

    def timelapse_last_at(self):
        files = sorted([file for file
                        in glob.glob(self.timelapse_path + '/*.mp4')
                        if os.path.isfile(file)])
        if not files:
            return None
        dt, _ = self._parse_timelapse_to_date_and_slot(files[-1])
        return dt

    def slot_to_timelapse(self, date: datetime.date, slot: int) -> Optional[str]:
        files = sorted([file for file
                        in glob.glob(self.timelapse_path + '/*.mp4')
                        if os.path.isfile(file) and
                        self._parse_timelapse_to_date_and_slot(file) == (date, slot)])
        if not files:
            return None
        if len(files) > 1:
            logger.warning(f"Multiple files matching slot {slot} and date {date.isoformat()} found")
        return files[0]

    @staticmethod
    def _timelapse_slot(dt: datetime.datetime) -> int:
        """Returns index of three-hour interval (1 to 9)"""
        return (dt.hour // 3) + 1

    def _make_fake_video(self, timelapse_video_name: str):
        timelapse_video_path = os.path.join(self.timelapse_path, timelapse_video_name)
        if not os.path.isfile(timelapse_video_path):
            os.system(f"touch {timelapse_video_path}")

    def _make_timelapse_video(self, slot_files: list, slot: int, timelapse_video_name: str):
        with tempfile.TemporaryDirectory(prefix='parklapse', dir=self.tmp_path) as tmpdirname:
            concat_video_path = os.path.join(tmpdirname, f"concatvideo_{slot}.mp4")
            if os.path.isfile(concat_video_path):
                logger.warning(f'Removing existing target {concat_video_path}')
                os.remove(concat_video_path)

            self._compose_concat_video(slot_files, concat_video_path)
            logger.info(f"Got composed video path: {concat_video_path}")

            tmp_timelapse_video_path = os.path.join(tmpdirname, timelapse_video_name)
            logger.info(f"Going to make timelapse video at: {tmp_timelapse_video_path}")
            self._compose_timelapse_video(concat_video_path, tmp_timelapse_video_path)
            logger.info(f"Video size: {os.stat(tmp_timelapse_video_path).st_size // (1024 * 1024)} MiB")
            shutil.move(tmp_timelapse_video_path, self.timelapse_path)

    def _deduce_slot_files(self, dt: datetime.datetime, slot: int) -> Optional[list]:
        slot_files = [file for file in self._enumerate_files() if
                      self._parse_raw_dt(file).date() == dt.date() and
                      self._timelapse_slot(self._parse_raw_dt(file)) == slot]
        if len(slot_files) < 1:
            logger.info("Nothing to do")
            return None
        for file in slot_files:
            logger.info(" - file " + file)
        # TODO debugging
        if True and slot_files:
            slot_files = [slot_files[0]]
            if len(slot_files) > 1:
                slot_files.append(slot_files[-1])
        return slot_files

    def produce_timelapse(self, dt: datetime.datetime, slot: int, read_only: bool, random_failure: bool) -> bool:
        # Returns True if timelapse was actually generated
        timelapse_video_base = self._make_timelapse_video_base(dt, slot)
        timelapse_video_name = timelapse_video_base + '.mp4'
        timelapse_err_name = timelapse_video_base + '.err'
        try:
            logger.info(f"Creating timelapse for date {dt.isoformat()} and slot {slot}")
            logger.info(f"Video name would be {timelapse_video_name}")
            if os.path.isfile(os.path.join(self.timelapse_path, timelapse_video_name)):
                logger.info(f"Target video already exists, skipping")
                return False

            slot_files = self._deduce_slot_files(dt, slot)
            if not slot_files:
                logger.info("Nothing to do")
                return False

            if os.path.isfile(os.path.join(self.timelapse_path, timelapse_err_name)):
                os.remove(os.path.join(self.timelapse_path, timelapse_err_name))
                logger.info(f"Error file for this video exists, try to generate again")

            if random_failure and slot == 2:
                raise RuntimeError('Random error!')

            if not read_only:
                # self._make_fake_video(timelapse_video_name)
                self._make_timelapse_video(slot_files, slot, timelapse_video_name)

            return True
        except Exception as e:
            logger.error(str(e))
            logger.exception(e)
            with open(os.path.join(self.timelapse_path, timelapse_err_name), 'wt') as f:
                f.write(datetime.datetime.now(datetime.timezone.utc).isoformat() + "\n")
                f.write(f"Video cannot be generated\n")
                f.write("Error: " + str(e) + "\n")

    @staticmethod
    def local_bin():
        if sys.platform.startswith('darwin'):
            return '/usr/local/bin'
        if sys.platform.startswith('linux'):
            return '/usr/bin'
        raise RuntimeError('wrong platform')

    @staticmethod
    def _make_timelapse_video_base(dt: datetime.datetime, slot: int) -> str:
        return "timelapse-{}_{}".format(dt.strftime('%Y%m%d'),
                                        slot)

    def _compose_concat_video(self, files: list, out_video_path: str):
        if not files:
            raise RuntimeError('No files')

        command = [os.path.join(self.local_bin(), 'mkvmerge')]
        for file in files:
            command.append(file)
            command.append('+')
        command.pop()
        command.extend([
            '-o',
            out_video_path])
        logger.info("Launching: " + " ".join(command))
        res = subprocess.run(command, shell=False, check=False,
                             stdout=None, stderr=subprocess.PIPE)
        if res.returncode != 0:
            raise RuntimeError('Concatenation failed ' + str(res.stderr.decode('latin-1')))
        logger.info("Succeed")

    def _compose_timelapse_video(self, in_video_path: str, out_video_path: str):
        bitrate = 4  # mbs
        fps = 24
        speedup = 60  # times

        command = [os.path.join(self.local_bin(), 'ffmpeg')]
        command.extend(['-hide_banner',
                        '-nostdin',
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

    def check_timelapses(self, read_only: bool, random_failure: bool):
        files = self._enumerate_files()
        if len(files) < 2:
            return

        first_dt = self._parse_raw_dt(files[0])
        last_dt = self._parse_raw_dt(files[-2])
        # run through them with a 1 hour stride
        dt = first_dt
        generated_count = 0
        slots = set()
        while dt <= last_dt:
            slot = self._timelapse_slot(dt)
            slots.add(slot)
            if self.produce_timelapse(dt, self._timelapse_slot(dt), read_only, random_failure):
                generated_count += 1

            dt = dt + datetime.timedelta(hours=1)

        logger.info(f"Check done, generated {generated_count}, total slots checked {len(slots)}")
        logger.info(f"Stats: success={self.timelapses_count()} errors={self.timelapses_error_count()}")

    def provide_timelapses(self) -> list:
        return [(file, *self._parse_timelapse_to_date_and_slot(file))
                for file
                in sorted(glob.glob(self.timelapse_path + '/*.mp4'))
                if os.path.isfile(file)]
