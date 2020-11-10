#!/usr/bin/env python3
# -*- coding:utf-8 -*-

"""Script content introduction
__author__ = 'ziying'
__date__ = '2020/11/1 14:23'
__function__ = '配置文件'
"""

import os
import redis


from configparser import ConfigParser


# 项目目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 配置文件
INI_PATH = os.path.join(BASE_DIR, 'config', 'config.ini')

# 日志目录
LOG_PATH = os.path.join(BASE_DIR, 'logs')

# 图片验证码Redis有效期， 单位：秒
IMAGE_CODE_REDIS_EXPIRES = 300

# 短信验证码Redis有效期，单位：秒
SMS_CODE_REDIS_EXPIRES = 300

# 七牛空间域名
QINIU_DOMIN_PREFIX = "http://ouwyn64sa.bkt.clouddn.com/"

# 城区信息redis缓存时间，单位：秒
AREA_INFO_REDIS_EXPIRES = 7200

# 首页展示最多的房屋数量
HOME_PAGE_MAX_HOUSES = 5

# 首页房屋数据的Redis缓存时间，单位：秒
HOME_PAGE_DATA_REDIS_EXPIRES = 7200

# 房屋详情页展示的评论最大数
HOUSE_DETAIL_COMMENT_DISPLAY_COUNTS = 30

# 房屋详情页面数据Redis缓存时间，单位：秒
HOUSE_DETAIL_REDIS_EXPIRE_SECOND = 7200

# 房屋列表页面每页显示条目数
HOUSE_LIST_PAGE_CAPACITY = 2

# 房屋列表页面Redis缓存时间，单位：秒
HOUSE_LIST_REDIS_EXPIRES = 7200

# 邮件信息

EMAIL_INFO = {
    'username': 'xxxxxx@qq.com',  # 切换成你自己的地址
    'password': 'xxxxxx',
    'smtp_host': 'smtp.qq.com',
    'smtp_port': 465
}

# 收件人
ADDRESSEE = [
    'xxxxxx@163.com',
]


class Config:
    """基本配置参数"""

    SECRET_KEY = "TQ6uZxn+SLqiLgVimX838/VpjasnfdjkalkjnalEP5jV7vvZ+Ohqw="

    # flask-sqlalchemy使用的参数
    SQLALCHEMY_DATABASE_URI = "mysql://root:mysql@localhost/love_home"  # 数据库
    SQLALCHEMY_TRACK_MODIFICATIONS = True  # 追踪数据库的修改行为，如果不设置会报警告，不影响代码的执行

    # 创建redis实例用到的参数
    REDIS_HOST = "127.0.0.1"
    REDIS_PORT = 6379

    # flask-session使用的参数
    SESSION_TYPE = "redis"  # 保存session数据的地方
    SESSION_USE_SIGNER = True  # 为session id进行签名
    SESSION_REDIS = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT)  # 保存session数据的redis配置
    PERMANENT_SESSION_LIFETIME = 86400  # session数据的有效期秒

    def __init__(self):

        config = ConfigParser()
        config.read(INI_PATH, 'utf-8')

        # 配置环境，SCE是生成环境, PE是测试环境
        self.environment = config.get("host", "host")
        # 用户名手机号
        self.username = config.get("data", "username")
        # 密码
        self.password = config.get("data", "password")
        # 验证码
        self.auth_code = config.get("data", "auth_code")
        # 错误密码
        self.error_pwd = config.get("data", "error_pwd")
        # 错误五位数密码
        self.five_pwd = config.get("data", "five_pwd")


class DevelopmentConfig(Config):
    """开发模式的配置参数"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境的配置参数"""
    pass


config = {
    "development": DevelopmentConfig,  # 开发模式
    "production": ProductionConfig  # 生产/线上模式
}


myconfig = Config()

if __name__ == '__main__':
    print(BASE_DIR)
