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

import boto3

logger = logging.getLogger(__name__)


class VideoService:

    def __init__(self, *args):
        if args:
            self.init_config(*args)

    # noinspection PyAttributeOutsideInit
    def init_config(self, raw_capture_path, timelapse_path, tmp_path, archive_path, bucket_name):
        self.raw_capture_path = raw_capture_path
        self.timelapse_path = timelapse_path
        self.tmp_path = tmp_path
        self.archive_path = archive_path
        self.bucket_name = bucket_name
        if not self.raw_capture_path or not os.path.isdir(self.raw_capture_path):
            raise RuntimeError('Bad raw_capture_path')
        if not self.timelapse_path or not os.path.isdir(self.timelapse_path):
            raise RuntimeError('Bad timelapse_path')
        if not self.archive_path or not os.path.isdir(self.archive_path):
            raise RuntimeError('Bad archive_path')
        if not self.bucket_name:
            raise RuntimeError('No bucket name')

    def _enumerate_raw_files(self) -> list:
        return list(sorted(file for file
                           in glob.glob(self.raw_capture_path + '/*/*.mp4')
                           if os.path.isfile(file)))

    def raw_count(self):
        return len(self._enumerate_raw_files())

    @staticmethod
    def _parse_raw_dt(fname: str) -> datetime.datetime:
        # out-20190602T1705.mp4
        m = re.match(r'out-(.*)\.mp4', os.path.basename(fname))
        if not m:
            raise ValueError('Wrong filename')
        return datetime.datetime.strptime(m.group(1), "%Y%m%dT%H%M")

    @staticmethod
    def _parse_timelapse_to_date_and_slot(fname: str) -> (datetime.date, int):
        # timelapse-slots-20190602_3.mp4
        m = re.match(r'timelapse-slots-(\d+)_(\d)\.mp4', os.path.basename(fname))
        if not m:
            raise ValueError('Wrong filename ' + fname)
        date = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        slot = int(m.group(2))
        logger.debug(f"Res: {date!r} {slot!r}")
        return date, slot

    @staticmethod
    def _parse_timelapse_daily_to_date(fname: str) -> datetime.date:
        # timelapse-daily-20190602.mp4
        m = re.match(r'timelapse-daily-(\d+)\.mp4', os.path.basename(fname))
        if not m:
            raise ValueError('Wrong filename ' + fname)
        dt = datetime.datetime.strptime(m.group(1), "%Y%m%d").date()
        logger.debug(f"Res: {dt!r}")
        return dt

    def raw_last_at(self) -> Optional[datetime.datetime]:
        files = self._enumerate_raw_files()
        if len(files) < 2:
            return None
        last_completed_file = files[-2]
        return self._parse_raw_dt(last_completed_file)

    def timelapses_error_count(self):
        return len([file for file
                    in glob.glob(self.timelapse_path + '/*.err')
                    if os.path.isfile(file)])

    def timelapses_slots_count(self):
        return len([file for file
                    in glob.glob(self.timelapse_path + '/timelapse-slots-*.mp4')
                    if os.path.isfile(file)])

    def timelapses_daily_count(self):
        return len([file for file
                    in glob.glob(self.timelapse_path + '/timelapse-daily-*.mp4')
                    if os.path.isfile(file)])

    def archives_count(self):
        return len([file for file
                    in glob.glob(self.archive_path + '/archive-*.ok')
                    if os.path.isfile(file)])

    def archives_error_count(self):
        return len([file for file
                    in glob.glob(self.archive_path + '/archive-*.err')
                    if os.path.isfile(file)])

    def timelapse_last_file(self):
        files = sorted([file for file
                        in glob.glob(self.timelapse_path + '/timelapse-slots-*.mp4')
                        if os.path.isfile(file)])
        if not files:
            return None
        return os.path.basename(files[-1])

    def timelapse_last_at(self):
        files = sorted([file for file
                        in glob.glob(self.timelapse_path + '/timelapse-slots-*.mp4')
                        if os.path.isfile(file)])
        if not files:
            return None
        dt, _ = self._parse_timelapse_to_date_and_slot(files[-1])
        return dt

    def get_timelapses_for_slot(self, date: datetime.date, slot: int) -> Optional[str]:
        files = sorted([file for file
                        in glob.glob(self.timelapse_path + '/timelapse-slots-*.mp4')
                        if os.path.isfile(file) and
                        self._parse_timelapse_to_date_and_slot(file) == (date, slot)])
        if not files:
            return None
        if len(files) > 1:
            logger.warning(f"Multiple files matching slot {slot} and date {date.isoformat()} found")
        return files[0]

    def get_timelapses_for_date(self, date: datetime.date) -> Optional[str]:
        files = sorted([file for file
                        in glob.glob(self.timelapse_path + '/timelapse-slots-*.mp4')
                        if os.path.isfile(file) and
                        self._parse_timelapse_to_date_and_slot(file)[0] == date])
        if not files:
            return None
        if len(files) > 1:
            logger.warning(f"Multiple files matching date {date.isoformat()} found")
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

            try:
                self._compose_concat_video(slot_files, concat_video_path)
            except Exception:
                # Check which file caused failure
                for slot_file in slot_files:
                    good, reason = self._is_good_video(slot_file)
                    if not good:
                        logger.error(f"Bad video {slot_file}: {reason}")
                raise
            logger.info(f"Got composed video path: {concat_video_path}")

            tmp_timelapse_video_path = os.path.join(tmpdirname, timelapse_video_name)
            logger.info(f"Going to make timelapse video at: {tmp_timelapse_video_path}")
            self._compose_timelapse_video(concat_video_path, tmp_timelapse_video_path)
            logger.info(f"Video size: {os.stat(tmp_timelapse_video_path).st_size // (1024 * 1024)} MiB")
            shutil.move(tmp_timelapse_video_path, self.timelapse_path)

    def _make_daily_timelapse_video(self, timelapse_files: list, timelapse_video_name: str):
        with tempfile.TemporaryDirectory(prefix='parklapse-daily-', dir=self.tmp_path) as tmpdirname:
            tmp_video_path = os.path.join(tmpdirname, timelapse_video_name)
            if os.path.isfile(tmp_video_path):
                logger.warning(f'Removing existing target {tmp_video_path}')
                os.remove(tmp_video_path)

            self._compose_concat_video(timelapse_files, tmp_video_path)
            logger.info(f"Got composed video path: {tmp_video_path}")

            logger.info(f"Video size: {os.stat(tmp_video_path).st_size // (1024 * 1024)} MiB")
            shutil.move(tmp_video_path, self.timelapse_path)

    def _deduce_slot_files(self, dt: datetime.datetime, slot: int) -> Optional[list]:
        slot_files = sorted([file for file in self._enumerate_raw_files() if
                             self._parse_raw_dt(file).date() == dt.date() and
                             self._timelapse_slot(self._parse_raw_dt(file)) == slot])
        if len(slot_files) < 1:
            logger.info("Nothing to do")
            return None
        for file in slot_files:
            logger.info(" - file " + file)
        return slot_files

    def _deduce_timelapses_for_day(self, date: datetime.date) -> Optional[list]:
        timelapse_files = sorted([file for file in
                                  glob.glob(self.timelapse_path + '/timelapse-slots-*.mp4')
                                  if os.path.isfile(file) and
                                  self._parse_timelapse_to_date_and_slot(file)[0] == date])
        if len(timelapse_files) < 1:
            logger.info("Nothing to do")
            return None
        for file in timelapse_files:
            logger.info(" - file " + file)
        return timelapse_files

    def produce_timelapse(self, dt: datetime.datetime, slot: int, read_only: bool, random_failure: bool) -> bool:
        # Returns True if timelapse was actually generated
        logger.info(f"Creating timelapse for date {dt.isoformat()} and slot {slot}")
        timelapse_video_base = self._make_timelapse_video_base(dt, slot)

        timelapse_video_name = timelapse_video_base + '.mp4'
        timelapse_err_name = timelapse_video_base + '.err'
        try:
            logger.info(f"Video name would be {timelapse_video_name}")
            if os.path.isfile(os.path.join(self.timelapse_path, timelapse_video_name)):
                logger.info(f"Target video already exists, skipping")
                return False

            if os.path.isfile(os.path.join(self.timelapse_path, timelapse_err_name)):
                os.remove(os.path.join(self.timelapse_path, timelapse_err_name))
                logger.info(f"Error file for this video exists, try to generate again")

            if random_failure:
                raise RuntimeError('Random error!')

            # specific code
            slot_files = self._deduce_slot_files(dt, slot)
            if not slot_files:
                logger.info("Nothing to do")
                return False

            if not read_only:
                self._make_timelapse_video(slot_files, slot, timelapse_video_base + '.mp4')
                return True

        except Exception as e:
            logger.error(str(e))
            logger.exception(e)
            with open(os.path.join(self.timelapse_path, timelapse_err_name), 'wt') as f:
                f.write(datetime.datetime.now(datetime.timezone.utc).isoformat() + "\n")
                f.write(f"Video cannot be generated\n")
                f.write("Error: " + str(e) + "\n")

    def produce_daily_timelapse(self, date: datetime.date, read_only: bool, random_failure: bool) -> bool:
        # Returns True if timelapse was actually generated
        logger.info(f"Creating timelapse for day date {date.isoformat()}")
        timelapse_video_base = self._make_timelapse_daily_video_base(date)

        timelapse_video_name = timelapse_video_base + '.mp4'
        timelapse_err_name = timelapse_video_base + '.err'
        try:
            logger.info(f"Video name would be {timelapse_video_name}")
            if os.path.isfile(os.path.join(self.timelapse_path, timelapse_video_name)):
                logger.info(f"Target video already exists, skipping")
                return False

            if os.path.isfile(os.path.join(self.timelapse_path, timelapse_err_name)):
                os.remove(os.path.join(self.timelapse_path, timelapse_err_name))
                logger.info(f"Error file for this video exists, try to generate again")

            if random_failure:
                raise RuntimeError('Random error!')

            # specific code

            timelapse_files = sorted(self._deduce_timelapses_for_day(date))
            if not timelapse_files:
                logger.info("Nothing to do")
                return False

            if not read_only:
                self._make_daily_timelapse_video(timelapse_files, timelapse_video_name)
                return True

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
        return "timelapse-slots-{}_{}".format(dt.strftime('%Y%m%d'),
                                              slot)

    @staticmethod
    def _make_timelapse_daily_video_base(dt: datetime.date) -> str:
        return "timelapse-daily-{}".format(dt.strftime('%Y%m%d'))

    @staticmethod
    def _make_archive_video_base(dt: datetime.date, hour: int) -> str:
        return "archive-{}_{}".format(dt.strftime('%Y%m%d'), hour)

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

    def _is_good_video(self, video_path: str) -> (bool, Optional[str]):
        if not video_path or not os.path.isfile(video_path):
            return False, None

        command = [os.path.join(self.local_bin(), 'ffprobe'), '-hide_banner', video_path]
        res = subprocess.run(command, shell=False, check=False,
                             stdout=None, stderr=subprocess.PIPE)
        if res.returncode != 0:
            return False, str(res.stderr.decode('latin-1'))
        return True, None

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
        files = self._enumerate_raw_files()
        if len(files) < 2:
            return

        now = datetime.datetime.now()

        first_dt = self._parse_raw_dt(files[0])
        last_dt = self._parse_raw_dt(files[-2])
        # run through them with a 1 hour stride
        dt = first_dt
        generated_slots_count = 0
        slots = set()
        days = set()
        while dt < last_dt:
            slot = self._timelapse_slot(dt)
            slots.add(slot)
            days.add(dt.date())

            if dt.date() == now.date() and self._timelapse_slot(dt) == self._timelapse_slot(now):
                logger.info("Skipping current slot")
            else:
                if self.produce_timelapse(dt, self._timelapse_slot(dt), read_only, random_failure):
                    generated_slots_count += 1

            dt = dt + datetime.timedelta(hours=1)

        logger.info(f"Check done, generated {generated_slots_count} slots tl, total slots checked {len(slots)}")

        # run through days
        generated_daily_count = 0
        if datetime.datetime.now().date() in days:
            days.remove(datetime.datetime.now().date())
        for day in days:
            if self.produce_daily_timelapse(day, read_only, random_failure):
                generated_daily_count += 1

        logger.info(f"Check done, generated {generated_daily_count} daily tl, checked {len(days)} days")

        logger.info(f"Stats: success={self.timelapses_daily_count()} errors={self.timelapses_error_count()}")

    def provide_timelapse_slots(self) -> list:
        return [(file, *self._parse_timelapse_to_date_and_slot(file))
                for file
                in sorted(glob.glob(self.timelapse_path + '/timelapse-slots-*.mp4'))
                if os.path.isfile(file)]

    def provide_timelapse_daily(self) -> list:
        return [(file, self._parse_timelapse_daily_to_date(file))
                for file
                in sorted(glob.glob(self.timelapse_path + '/timelapse-daily-*.mp4'))
                if os.path.isfile(file)]

    def _generate_archive(self, date: datetime.date, hour: int, read_only: bool) -> bool:
        logging.info(f"Building archive for {date}:{hour}")
        archive_video_base = self._make_archive_video_base(date, hour)
        archive_status_path = os.path.join(self.archive_path, archive_video_base + '.ok')
        archive_error_path = os.path.join(self.archive_path, archive_video_base + '.err')
        archive_video_path = os.path.join(self.archive_path, archive_video_base + '.mp4')

        if os.path.isfile(archive_status_path):
            logging.info("Already done")
            return False
        if os.path.isfile(archive_error_path):
            logging.info("Already errored")
            return False

        try:

            if os.path.isfile(archive_video_path):
                logging.info("Already here, removing")
                os.remove(archive_video_path)

            files = sorted([file for file in self._enumerate_raw_files() if
                            self._parse_raw_dt(file).date() == date and
                            self._parse_raw_dt(file).hour == hour and
                            self._is_good_video(file)])
            logging.info("Files are: " + repr(files))
            logging.info("Target is: " + archive_video_path)

            if not files:
                logging.info("No files found")
                return False

            command = [os.path.join(self.local_bin(), 'ffmpeg'),
                       '-hide_banner',
                       '-nostdin',
                       '-threads',
                       '1']
            # ffmpeg -i out-20190604T1706.mp4  -i out-20190604T1716.mp4  -filter_complex \
            # "[0:v:0]fps=8,scale=1280:720,format=yuvj420p[v0];\
            # [1:v:0]fps=8,scale=1280:720,format=yuvj420p[v1];\
            # [v0][v1]concat=n=2:v=1[outv]" \
            # -map "[outv]" -c:v libx264 -crf 26 -maxrate 1000K -bufsize 1600K output.mp4
            for file in files:
                command.extend(['-i',
                                file])
            filter_expr = ''
            filter_expr += ''.join([str(f'[{m}:v:0]fps=8,scale=1280:720,format=yuvj420p[v{m}];')
                                    for m, _ in enumerate(files)])
            filter_expr += ''.join([str(f'[v{m}]')
                                    for m, _ in enumerate(files)])
            filter_expr += f'concat=n={len(files)}:v=1[outv]'
            command.extend(['-filter_complex',
                            filter_expr])
            expr = '-map [outv] -c:v libx264 -crf 26 -maxrate 1000K -bufsize 1600K'
            command.extend(expr.split(' '))
            command.extend([archive_video_path])
            logger.info("Launching: " + " ".join(command))
            res = subprocess.run(command, shell=False, check=False,
                                 stdout=None, stderr=subprocess.PIPE)
            if res.returncode != 0:
                raise RuntimeError('Remux failed ' + str(res.stderr.decode('latin-1')))
            logger.info("Succeed")

            self._upload_to_s3(archive_video_base + '.mp4', archive_video_path)

            logger.info("Uploaded to s3")

            shutil.move(archive_video_path, self.tmp_path)

            # Mark as completed
            with open(archive_status_path, 'wt') as f:
                f.write('ok')

            logger.info("Marked as completed")

            logger.info("Rename original files")
            for file in files:
                os.rename(file, file + '.del')

            logger.info("Done archiving")
            return True

        except Exception as e:
            logger.error(str(e))
            logger.exception(e)
            with open(archive_error_path, 'wt') as f:
                f.write(datetime.datetime.now(datetime.timezone.utc).isoformat() + "\n")
                f.write(f"Video cannot be archived\n")
                f.write("Error: " + str(e) + "\n")
            return False

    def _upload_to_s3(self, name, path):
        s3_client = boto3.client('s3')
        s3_client.upload_file(path, self.bucket_name, name)

    def archive(self, read_only: bool):
        dates = sorted(list({self._parse_raw_dt(file).date() for file in self._enumerate_raw_files()}))
        logging.info(f"Found raw files for {len(dates)} dates: {repr(dates)}")

        dates = [date for date in dates
                 if abs(date - datetime.date.today()) > datetime.timedelta(days=2)]
        dates = dates[0]
        for date in dates:
            for hour in range(0, 24):
                self._generate_archive(date, hour, read_only)


class StatsService:
    def collect_stats(self, video_service: VideoService) -> dict:
        stats = dict()
        stats['alive'] = True
        stats['stats_at'] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
        try:
            stats['raw_count'] = video_service.raw_count()
            if video_service.raw_last_at():
                stats['raw_last_at'] = video_service.raw_last_at().replace(microsecond=0).isoformat()
            stats['timelapses_daily_count'] = video_service.timelapses_daily_count()
            stats['timelapses_success_count'] = video_service.timelapses_slots_count()
            stats['timelapses_error_count'] = video_service.timelapses_error_count()
            stats['timelapse_last_file'] = video_service.timelapse_last_file()
            stats['archives_count'] = video_service.archives_count()
            stats['archives_error_count'] = video_service.archives_error_count()
            if video_service.timelapse_last_at():
                stats['timelapse_last_at'] = video_service.timelapse_last_at().isoformat()
        except Exception as e:
            logger.error(e)
            stats['error'] = str(e)

        stats = {k: v for k, v in stats.items() if v is not None}
        return stats
