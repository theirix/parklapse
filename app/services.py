import datetime
import glob
import logging
import os
import re


class VideoService:
    logger = logging.getLogger(__name__)

    def __init__(self, raw_capture_directory):
        self.raw_capture_directory = raw_capture_directory

    def _enumerate_files(self) -> list:
        return list(sorted(file for file
                           in glob.glob(self.raw_capture_directory + '/*/*.mp4')
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
        if not files:
            return None
        last_file = files[-1]
        return self._parse_dt(last_file)
