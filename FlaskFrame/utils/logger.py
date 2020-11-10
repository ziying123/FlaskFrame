#!/usr/bin/env python3
# -*- coding:utf-8 -*-


"""Script content introduction
__author__ = 'ziying'
__date__ = '2020/10/31 11:06'
__function__ = 'xxx'
"""


import os
import logging

from FlaskFrame.config.conf import LOG_PATH
from FlaskFrame.utils.times import datetime_strftime


class Log:
    """
    自定义日志封装
    """
    def __init__(self, sort):
        self.sort = sort
        self.logger = logging.getLogger()
        if not self.logger.handlers:
            self.logger.setLevel(logging.DEBUG)

            # 创建一个handle写入文件
            fh = logging.FileHandler(self.log_path, encoding='utf-8')
            fh.setLevel(logging.INFO)

            # 创建一个handle输出到控制台
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)

            # 定义输出的格式
            formatter = logging.Formatter(self.fmt)
            fh.setFormatter(formatter)
            ch.setFormatter(formatter)

            # 添加到handle
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)

    @property
    def log_path(self):

        log_path = os.path.join(LOG_PATH, self.sort)

        if not os.path.exists(log_path):
            os.makedirs(log_path)
        return os.path.join(log_path, '{}.log'.format(datetime_strftime("%Y%m%d%H%M")))

    @property
    def fmt(self):
        return '%(asctime)s %(name)s %(levelname)s %(filename)s [第%(lineno)d行] 日志详情：%(message)s'


if __name__ == '__main__':
    Logger = Log('user')
    Logger.logger.info('你好')
