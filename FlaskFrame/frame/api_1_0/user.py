# -*- coding: utf-8 -*-

# 导入蓝图对象api
from . import api

# 导入flask插件
from flask import current_app, jsonify, make_response, request, session, g

# 导入图片验证码扩展包
from FlaskFrame.utils.captcha.captcha import captcha

# 导入redis数据库实例， sqlalchemy实例， 常量文件
from FlaskFrame.frame import redis_store, db

# 导入自定义状态码
from FlaskFrame.utils.response_code import RET

# 导入云通讯接口， 发送短信
from FlaskFrame.utils import sms

# 导入模型类User
from FlaskFrame.frame.models import User

# 导入正则模块
import re

# 导入随机数模块
import random

# 导入登陆装饰器
from FlaskFrame.utils import login_required

# 导入七牛云接口
from FlaskFrame.utils.image_storage import storage

from FlaskFrame.utils.logger import Log


# 初始化log日志参数路径
logger = Log('user').logger


@api.route('/imagecode/<image_code_id>', methods=["GET"])
def generate_image_code(image_code_id):
    '''
    *生成验证码*
    1. 调用验证码生成函数
    2. 将验证码保存在redis缓存中
    3. 返回前端
    4. 设置头信息
    :param image_code_id:
    :return:
    '''

    # 调用验证码生成函数
    name, text, image = captcha.generate_captcha()  # 调用验证码

    # 试着将验证码保存到redis缓存中
    try:
        redis_store.setex("ImageCode_" + image_code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)
        logger.info("写入缓存验证码成功")
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询失败")

    # 返回结果
    else:
        response = make_response(image)
        response.headers["Content-Type"] = "image/jpg"
        return response


@api.route('/smscode/<mobile>', methods=["GET"])
def send_msg_code(mobile):
    '''
    *发送短信验证码*
    1. 获取参数（mobile, text, id)
    2. 校验参数的完整性
    3. 校验手机号的正则
    4. 从redis缓存中获取真实的图片验证码
    5. 判断真实验证码吗的有效期
    6. 从redis缓存中删除真实验证码
    7. 对比验证码的正确性
    8. 生成短信随机数
    9. 保存随机码到redis缓存
    10. 判断用户是否已经注册
    11. 调用接口发送验证码啊
    12. 判断发送结果
    13. 返回结果
    :param mobile:
    :return:
    '''

    # 获取请求参数
    image_code = request.args.get("text")
    image_code_id = request.args.get("id")

    # 校验完整性
    if not all([mobile, image_code, image_code_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不完整")

    # 校验手机号
    if not re.match(r'1[3456789]\d{9}$', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号格式不正确")

    # 获取真实验证码
    try:
        real_image_code = redis_store.get("ImageCode_" + image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="获取验证码斯失败")

    # 校验获取验证码
    if not real_image_code:
        return jsonify(errno=RET.NODATA, errmsg="验证码过期")

    # 删除验证码
    try:
        redis_store.delete("ImageCode_" + image_code_id)
    except Exception as e:
        current_app.logger.error(e)

    # 比较验证码是否一致
    if real_image_code.lower() != image_code.lower():
        return jsonify(errno=RET.DATAERR, errmsg="验证码不正确")

    # 生成短信随机码
    sms_code = "%06d" % random.randint(1, 999999)

    # 保存随机数
    try:
        redis_store.setex("SMSCode_" + mobile, constants.SMS_CODE_REDIS_EXPIRES, sms_code)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="保存随机数失败")

    # 判断手机号是否注册
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询失败")
    else:
        if user:
            return jsonify(errno=RET.DBERR, errmsg="手机号已经注册")

    # 调用接口， 发送激活短信
    try:
        ccp = sms.CCP()
        # 保存发送的结果
        result = ccp.send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES / 60], 1)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="发送短信异常")

    # 判断发送结果
    if result == 0:
        return jsonify(errno=RET.OK, errmsg="发送成功")
    else:
        return jsonify(errno=RET.THIRDERR, errmsg="发送失败")


@api.route('/users', methods=["POST"])
def register():
    '''
    *注册用户提交*
    1. 获取参数 request.get_json()
    2. 校验参数的存在
    3. 进一步获取参数信息 user_data.get("")
    4. 校验参数的完整性 all()
    5. 校验手机号的正则
    6. 获取本地存储的真实的短信验证码
    7. 校验短信验证码的有效期
    8. 对比验证码是否一致
    9. 删除redis缓存里的短信验证码
    10. 判断是否注册
    11. 保存用户信息
    12. 加密密码信息 user.password = password
    13. 提交到数据库 db..session.add(user) db.session.commit() 出错则进行回滚操作db.sesion.rollback()
    14. 将用户信息缓存到session中 session["user_id"] = user.id  name mobile
    15. 返回结果 额外返回一个 data=user.to_dict()
    :return:
    '''

    # 获取参数
    user_data = request.get_json()

    # 校验参数存在
    if not user_data:
        return jsonify(errno=RET.PARAMERR, errmsg="参数缺失")

    # 进一步获取参数
    mobile = user_data.get("mobile")
    smscode = user_data.get("sms_code")
    password = user_data.get("password")

    # 校验参数的完整性
    if not all([mobile, smscode, password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不完整")

    # 对手机号进行校验
    if not re.match(r'1[3456789]\d{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号格式不正确")

    # 获取本地存储的真实验证码
    try:
        real_sms_code = redis_store.get("SMSCode_" + mobile)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="获取失败")

    # 判断获取的结果
    if not real_sms_code:
        return jsonify(errno=RET.NODATA, errmsg="短信验证码失效")

    # 比较短信验证码是否一致
    if real_sms_code != str(smscode):
        return jsonify(errno=RET.DATAERR, errmsg="验证码不正确")

    # 删除redis中存储的短信验证码
    try:
        redis_store.delete("SMSCode_" + mobile)
    except Exception as e:
        current_app.logger.error(e)

    # 判断是否注册
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询失败")
    else:
        if user:
            return jsonify(errno=RET.DATAEXIST, errmsg="用户已经存在")

    # 保存用户信息
    user = User(name=mobile, mobile=mobile)

    # 加密密码
    user.password = password

    # 提交到数据库
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存用户信息失败")

    # 缓存用户信息到redis缓存中
    session['user_id'] = user.id
    session['name'] = mobile
    session['mobile'] = mobile

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK", data=user.to_dict())


@api.route('/sessions', methods=['POST'])
def login():
    '''
    *用户登陆*
    1. 获取参数
    2. 校验参数的存在
    3. 进一步获取详细参数
    4. 检验参数的完整性
    5. 判断手机号
    6. 判断手机号是否已经注册
    7. 校验用户名以及密码
    8. 缓存用户信息
    9. 返回结果
    :return:
    '''

    # 获取参数
    user_data = request.get_json()

    # 校验参数存在
    if not user_data:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不存在")

    # 进一步获取详细参数
    mobile = user_data.get("mobile")
    password = user_data.get("password")

    # 校验参数的完整性
    if not all([mobile, password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不完整")

    # 校验手机号的正则
    if not re.match(r'1[3456789]\d{9}', mobile):
        return jsonify(errno=RET.PARAMERR, errmsg="手机号格式不对")

    # 查询mysql数据库，判断用户的存在与否
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询失败")

    # 校验查询结果， 以及对密码进行判断
    if user is None or not user.check_password(password):
        return jsonify(errno=RET.DATAEXIST, errmsg="用户名或密码错误")

    # 缓存用户信息到redis缓存中
    session['user_id'] = user.id
    session['name'] = user.name
    session['mobile'] = mobile

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK", data={"user_id": user.id})


@api.route('/user', methods=["GET"])
@login_required
def get_user_profile():
    '''
    *获取用户信息*
    1. 通过登陆装饰器获取用户身份信息
    2. 根据user_id 查询数据
    3. 判断查询结果
    4. 返回结果
    :return:
    '''

    # 获取用户身份id
    user_id = g.user_id

    # 查询mysql数据库
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询失败")

    # 判断存在与否
    if not user:
        return jsonify(errno=RET.NODATA, errmsg="数据不存在")

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK", data=user.to_dict())


@api.route('/user/name', methods=['PUT'])
@login_required
def change_user_profile():
    '''
    *修改用户名*
    1. 获取用户身份
    2. 校验参数存在
    3. 获取详细参数
    4. 校验name
    5. 查询数据库， 保存更新后的name
    6. 更新redis里面的用户名
    7. 返回结果
    :return:
    '''

    # 获取用户id
    user_id = g.user_id

    # 获取put请去参数
    user_name = request.get_json()

    # 判断参数存在
    if not user_name:
        return jsonify(errno=RET.PARAMERR, ermsg="无参数")

    # 获取name参数
    name = user_name.get("name")

    # 校验name
    if not name:
        return jsonify(errno=RET.PARAMERR, errmsg="获取失败")

    # 更新用户信息
    try:
        User.query.filter_by(id=user_id).update({"name": name})
        # 提交事务
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 抛出异常，进行事务的回滚
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    # 缓存数据更新redis
    session['name'] = name

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK", data={"name": name})


@api.route('/user/avatar', methods=["POST"])
@login_required
def set_user_avatar():
    '''
    *上传用户头像*
    1. 获取用户身份信息
    2. 获取图片文件的参数信息
    3. 校验参数
    4. 读取图片文件，传入七牛云
    5. 调用七牛云， 上传图片， 返回图片名称
    6. 保存图片名称到mysql
    7. 提交事务
    8. 拼接图片的绝对路径
    9. 返回结果
    :return:
    '''

    # 获取用户id
    user_id = g.user_id

    # 获取图片文件参数
    avatar = request.files.get("avatar")

    # 校验数据
    if not avatar:
        return jsonify(errno=RET.PARAMERR, errmsg="获取数据失败")

    # 读取图片数据
    avatar_data = avatar.read()

    # 调用七牛云接口
    try:
        image_name = storage(avatar_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="接口异常")

    # 保存图片到数据库
    try:
        User.query.filter_by(id=user_id).update({"avatar_url": image_name})
        # 提交事务
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        # 回滚事务
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    # 拼接返回给前段的图片绝对路径
    image_url = constants.QINIU_DOMIN_PREFIX + image_name

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK", data={"avatar_url": image_url})


@api.route('/user/auth', methods=["POST"])
@login_required
def set_user_auth():
    '''
    *设置用户实名信息*
    1. 获取用户身份
    2. 获取POST请求参数
    3. 校验参数的存在
    4. 进一步获取详细的参数信息 real_name id_card
    5. 校验参数的完整性
    6. 操作mysql， 保存用户的实名信息
    7. 提交数据
    8. 返回结果
    :return:
    '''

    # 获取用户ID
    user_id = g.user_id

    # 获取参数
    user_data = request.get_json()

    # 校验参数存在与否
    if not user_data:
        return jsonify(errno=RET.PARAMERR, errmsg="无参数")

    # 进一步获取详细参数
    real_name = user_data.get("real_name")
    id_card = user_data.get("id_card")

    # 校验参数完整性
    if not all([real_name, id_card]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不完整")

    # 校验姓名
    if not re.match(r'[\u4e00-\u9fff\w]{5,16}$', real_name):
        return jsonify(errno=RET.PARAMERR, errmsg="姓名格式不对")

    # 校验身份证号
    if not re.match(r'\d{17}[0123456789X]$', id_card):
        return jsonify(errno=RET.PARAMERR, errmsg="身份证号错误")

    # 保存用户实名信息
    try:
        User.query.filter_by(id=user_id, real_name=None, id_card=None).update({"real_name": real_name,
                                                                               "id_card": id_card})
        # 提交事务
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK")


@api.route('/user/auth', methods=["GET"])
@login_required
def get_user_auth():
    '''
    *获取用户实名信息*
    1. 获取用户身份
    2. 查询信息
    3. 校验查询结果
    4. 返回结果
    :return:
    '''

    # 获取用户ID
    user_id = g.user_id

    # 查询mysql数据库
    try:
        user = User.query.filter_by(id=user_id).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    # 校验结果
    if not user:
        return jsonify(errno=RET.NODATA, errmsg="无效操作")

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK", data=user.auth_to_dict())


@api.route('/session', methods=['DELETE'])
@login_required
def logout():
    '''
    *退出登陆*
    session.clear()
    :return:
    '''

    session.clear()
    return jsonify(errno=RET.OK, errmsg="OK")


@api.route('/session', methods=['GET'])
def check_login():
    '''
    检查用户登陆状态
    1. 使用请求上下文对象， session获取用户缓存信息
    2. 判断获取结果是否有数据， 如果有数据，返回/name
    3. 否则返货错误信息
    :return:
    '''

    # 从redis数据库获取用户缓存信息
    name = session.get("name")

    # 判断获取结果
    if name is not None:
        return jsonify(errno=RET.OK, errmsg="true", data={"name": name})
    else:
        return jsonify(errno=RET.SESSIONERR, errmsg="false")
