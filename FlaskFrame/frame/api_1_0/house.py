# -*- coding: utf-8 -*-

# 导入蓝图对象
from . import api

# 导入flask内置函数对象
from flask import current_app, jsonify, g, request, session

# 导入redis实例， 常量， splalchemy实例
from FlaskFrame.frame import redis_store,  db

# 导入模型类对象
from FlaskFrame.frame.models import Area, House, Facility, HouseImage, User, Order

# 导入自定义状态码
from FlaskFrame.utils.response_code import RET

# 导入登陆装饰器
from FlaskFrame.utils.commons import login_required

# 导入七牛云接口
from FlaskFrame.utils.image_storage import storage

from FlaskFrame.utils.logger import Log

# 导入json
import json

import datetime

# 初始化log日志参数路径
logger = Log('house').logger


@api.route('/areas', methods=['GET'])
def get_area_info():
    '''
    获取区域信息： 缓存-磁盘-缓存
    1. 尝试从redis中获取缓存数据信息
    2. 获取区域信息， 发送异常就将其置为None
    3. 判断获取结果
    4. 留下访问记录
    5. 缓存中的区域信息 已经是json 可以直接返回
    6. 查询mysql数据库
    7. 校验查询结果
    8. 定义容器， 存储查询结果， 遍历区域信息
    9. 转换为json 存入redis缓存
    10. 返回结果
    :return:
    '''

    # 尝试从缓存中获取信息
    try:
        areas = redis_store.get("area_info")
    except Exception as e:
        current_app.logger.error(e)
        # 没有进行返回， 则将其置为None
        areas = None

    # 判断获取结果， 留下查询记录
    if areas:
        current_app.logger.info('hit area info redis')
        return '{"errno": 0, "errmsg": "OK", "data": %s}' % areas

    # 查询数据库
    try:
        areas = Area.query.all()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询失败")

    # 校验查询结果
    if not areas:
        return jsonify(errno=RET.NODATA, errmsg="无信息")

    # 定义列表
    areas_list = []
    for area in areas:
        areas_list.append(area.to_dict())

    # 序列化数据， 准备加入缓存
    areas_json = json.dumps(areas_list)

    # 存入redis
    try:
        redis_store.setex('area_info', constants.AREA_INFO_REDIS_EXPIRES, areas_json)
    except Exception as e:
        current_app.logger.error(e)

    # 构造响应数据
    resp = '{"errno": 0, "errmsg": "OK, "data": %s}' % areas_json

    # 返回结果
    return resp


@api.route('/houses', methods=['POST'])
@login_required
def save_house_info():
    '''
    *保存房屋信息*
    1. 获取用户信息
    2. 获取参数
    3. 校验参数存在
    4. 获取详细参数
    5. 校验参数完整性
    6. 对价格参数处理， 元--》分
    7. 构造模型类对象， 准备保存房屋数据
    8. 尝试获取配套设施参数信息
    9. 如果有配套设施， 进行查询
    10. 提交数据
    11. 返回结果
    :return:
    '''

    # 获取用户身份
    user_id = g.user_id

    # 获取房屋参数
    house_data = request.get_json()

    # 校验参数存在
    if not house_data:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不存在")

    # 获取详细参数
    title = house_data.get("title")  # 房屋名称
    price = house_data.get("price")  # 房屋价格
    area_id = house_data.get("area_id")  # 房屋区域
    address = house_data.get("address")  # 房屋详细地址
    room_count = house_data.get("room_count")  # 房屋数目
    acreage = house_data.get("acreage")  # 房屋面积
    unit = house_data.get("unit")  # 房屋户型
    capacity = house_data.get("capacity")  # 房屋宜居住人数
    beds = house_data.get("beds")  # 房屋卧床配置
    deposit = house_data.get("deposit")  # 房屋押金
    min_days = house_data.get("min_days")  # 房屋最少入住天数
    max_days = house_data.get("max_days")  # 房屋最大入住天数

    # 校验参数完整性
    if not all([title, price, area_id, address, room_count,
                acreage, unit, capacity, beds, deposit, min_days, max_days]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数不完整")

    # 对金额进行准换
    try:
        price = int(float(price) * 100)
        deposit = int(float(deposit) * 100)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DATAERR, errmsg="准换失败")

    # 构造模型类对象
    house = House()
    house.user_id = user_id
    house.title = title
    house.price = price
    house.area_id = area_id
    house.address = address
    house.room_count = room_count
    house.acreage = acreage
    house.unit = unit
    house.capacity = capacity
    house.beds = beds
    house.deposit = deposit
    house.min_days = min_days
    house.max_days = max_days

    # 尝试获取配套设施
    facility = house_data.get("facility")

    # 如果存在， 过滤编号
    if facility:
        try:
            facilities = Facility.query.filter(Facility.id.in_(facility)).all()
            # 保存设施
            house.facilities = facilities
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    # 提交数据
    try:
        db.session.add(house)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存失败")

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK", data={"house_id": house.id})


@api.route('/houses/<house_id>/images', methods=["POST"])
@login_required
def save_house_image(house_id):
    '''
    *保存房屋图片*
    1. 获取参数
    2. 校验图片参数存在
    3. 根据house_id查询数据库， 确认房屋存在
    4. 校验查询结果
    5. 读取图片数据
    6. 调用器牛云接口
    7. 构造模型类
    8. 判断房屋图片是否设置， 否则设置为主页图片
    9. 提交数据到数据库
    10. 拼接图片路径
    11. 返回结果
    :param house_id:
    :return:
    '''

    # 获取图片参数
    image = request.files.get("house_image")

    # 校验参数存在
    if not image:
        return jsonify(errno=RET.PARAMERR, errmsg="参数不存在")

    # 根据house_id 查询数据库， 确认房屋存在
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    # 校验查询结果
    if not house:
        return jsonify(errno=RET.NODATA, errmsg="无效操作")

    # 读取图片数据
    image_data = image.read()

    # 调用七牛云接口
    try:
        image_name = storage(image_data)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="第三方错误")

    # 构造HouseImage模型类对象， 保存图片
    house_image = HouseImage()
    house_image.house_id = house_id
    house_image.url = image_name

    # 存入数据库会话中
    db.session.add(house_image)

    # 判断房屋主图片
    if not house.index_image_url:
        house.index_image_url = image_name
        db.session.add(house)

    # 提交数据
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="数据库异常")

    # 拼接图片绝对路径
    image_url = constants.QINIU_DOMIN_PREFIX + image_name

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK", data={"url": image_url})


@api.route('/user/houses', methods=['GET'])
@login_required
def get_user_houses():
    '''
    获取用户发布的房源
    1. 获取用户的身份信息user_id
    2. 根据user_id 查询数据库， 确认用户的存在
    3. 通过反向应用， 获取该用户的房屋信息
    4. 定义容器， 存储查询结果
    5. 判断如果有房源数据， 进行遍历
    6. 返回结果
    :return:
    '''

    # 获取用户身份信息
    user_id = g.user_id

    # 根据user_id 查询mysql数据库
    try:
        user = User.query.get(user_id)
        # 反向引用， 获取该用户发布的房源
        houses = user.houses
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询失败")

    # 定义容器
    houses_list = []

    # 判断数据
    if houses:
        for house in houses:
            houses_list.append(house.to_basic_dict())

    # 返回结果
    return jsonify(errno=RET.OK, errmsg="OK", data={"houses": houses_list})


@api.route('/houses/index', methods=['GET'])
def get_houses_index():
    '''
    获取房屋首页幻灯片信息： 缓存-磁盘-缓存
    1. 尝试从redis中获取幻灯片数据
    2. 校验结果， 如果有数据， 记录访问时间， 返回结果
    3. 查询/mysql数据库
    4. 校验结果
    5. 定义容器， 遍历存储结果， 判断是否设置房屋主图片， 如果为设置默认不添加
    6. 对房屋数据进行序列化 转换为json
    7. 对房屋数据存入缓存
    8. 返回结果
    :return:
    '''

    #  尝试从redis中获取缓存
    try:
        ret = redis_store.get('home_page_data')
    except Exception as e:
        current_app.logger.error(e)
        ret = None

    # 判断获取结果， 如果有数据， 记录访问时间，返回结果
    if ret:
        current_app.logger.info('hit house index info redis')
        return '{"errno": 0, "errmsg": "OK", "data": %s}' % ret

    # 查询mysql数据库
    try:
        # 查询房屋表， 默认按照成交量从高到底排序， 返回五条数据
        houses = House.query.order_by(House.order_count.desc()).limit(constants.HOME_PAGE_MAX_HOUSES)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询失败")

    # 校验查询结果
    if not houses:
        return jsonify(errno=RET.NODATA, errmsg="无房屋数据")

    # 定义容器， 遍历查询结果， 添加数据
    houses_list = []

    # 对房屋主图片是否设置进判断
    for house in houses:
        if not house.index_image_url:
            continue
        houses_list.append(house.to_basic_dict())

    # 序列化数据
    houses_json = json.dumps(houses_list)

    # 把房屋数据存入缓存
    try:
        redis_store.setex("home_page_data", constants.HOME_PAGE_DATA_REDIS_EXPIRES, houses_json)
    except Exception as e:
        current_app.logger.error(e)

    # 构造响应报文， 返回结果
    resp = '{"errno":0, "errmsg":"OK", "data":%s}' % houses_json
    return resp


@api.route('/houses/<int:house_id>', methods=['GET'])
def get_house_detail(house_id):
    '''
    获取房屋详情数据： 缓存-磁盘-缓存
    1. 尝试确认用户身份， 把用户分为两类， 登陆用户获取user_id , 为登陆用户默认为-1 session.get('user_id', "-1")
    2. 校验house_id
    3. 操作redis数据库， 尝试获取房屋信息
    4. 判断获取结果， 如果有数据， 记录访问时间， 返回json数据
    5. 查询mysql数据库
    6. 校验查询结果， 确认房屋存在
    7. 调用模型类中的to_full_dict()
    8. 对房屋详情数据进行序列化， 存入redis缓存
    9. 构造响应数据
    10. 返回结果， user_id和房屋详情数据
    :param house_id:
    :return:
    '''

    # 尝试获取用户身份， 如果为登陆默认-1
    user_id = session.get('user_id', "-1")

    # 校验house_id
    if not house_id:
        return jsonify(errno=RET.PARAMERR, errmsg="参数缺失")

    # 根据house_id, 尝试从redis获取房屋数据
    try:
        ret = redis_store.get('house_info_%s' % house_id)
    except Exception as e:
        current_app.logger.error(e)
        ret = None

    # 判断获取结果
    if ret:
        current_app.logger.info('hit house detail info redis')
        return '{"errno": 0, "errmsg": "OK", "data": {"user_id": %s, "house": %s}}' % (user_id, ret)

    # 查询mysql数据库， 确认房屋存在
    try:
        house = House.query.get(house_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询房屋数据失败")

    # 校验查询结果
    if not house:
        return jsonify(errno=RET.NODATA, errmsg="无数据")

    # 调用模型类中的方法， 获取房屋详情数据
    try:
        house_data = house.to_full_dict()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="获取房屋详情失败")

    # 序列化数据
    house_json = json.dumps(house_data)

    # 把房屋详情数据存入到redis缓存里面
    try:
        redis_store.setex('house_info_%s' % house_id, constants.HOUSE_DETAIL_REDIS_EXPIRE_SECOND, house_json)
    except Exception as e:
        current_app.logger.error(e)

    # 构造响应报文
    resp = '{"errno":0, "errmsg":"OK", "data":{"user_id":%s, "house":%s}}' % (user_id, house_json)

    # 返回结果
    return resp


@api.route('/houses', methods=['GET'])
def get_houses_list():
    '''
    获取房屋列表信息  缓存-磁盘-缓存
    1. 尝试获取参数
    2. 对日期参数进行格式化
    3. 确认用户选择的开始日期和结束日期至少1天
    4. 对页数进行格式化
    5. 尝试从redis中获取房屋列表信息
    6. 构造键 redis_key = 'houses_%s_%s_%s_%s' % (area_id, start_date_str, end_date_str, sort_key)
    7. 判断获取结果
    8. 查询mysql
    9. 定义容器， 存储查询的过滤条件
    10. 对满足条件的房屋数据排序
    11. 对排序的数据进行分页
    12. 定义容器， 遍历分页后的数据
    13. 构造响应报文
    14. 对数据进行序列化， 转化为json
    15. 判断用户请求页数
    16. 多条数据插入到redis需要使用事务, 为了保证有效期一致
    17. 返回结果
    :return:
    '''

    # 获取参数
    area_id = request.args.get("aid", "")
    start_date_str = request.args.get("sd", "")
    end_date_str = request.args.get("ed", "")
    sort_key = request.args.get("sk", "")
    page = request.args.get("p", 1)

    # 对日期格式化
    try:
        start_date, end_date = None, None

        # 判断用户如果有开始或者结束日期
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')

        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')

        # 判断用户选择的日期
        if start_date_str and end_date_str:
            assert start_date <= end_date
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="日期参数错误")

    # 对页码进行格式化
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 尝试从redis中获取缓存
    try:
        redis_key = 'houses_%s_%s_%s_%s' % (area_id, start_date_str, end_date_str, sort_key)
        ret = redis_store.hget(redis_key, page)
    except Exception as e:
        current_app.logger.error(e)
        ret = None

    # 判断结果
    if ret:
        current_app.logger.info('hit houses list info redis')
        return ret

    # 查询mysql
    try:
        # 存储查询的过滤条件
        params_filter = []

        # 判断区域信息存在
        if area_id:
            params_filter.append(House.area_id == area_id)  # 返回的是一个对象

        # 日期判断
        if start_date and end_date:
            conflict_orders = Order.query.filter(Order.begin_date <= end_date, Order.end_date >= start_date).all()

            # 遍历有冲突的订单
            conflict_houses_id = [order.house_id for order in conflict_orders]

            # 判断有冲突的房屋存在
            if conflict_houses_id:
                # 取反
                params_filter.append(House.id.notin_(conflict_houses_id))

        elif start_date:
            # 查询
            conflict_orders = Order.query.filter(Order.end_date >= start_date).all()

            # 遍历有冲突的订单
            conflict_houses_id = [order.house_id for order in conflict_orders]

            # 判断有冲突的房屋存在
            if conflict_houses_id:
                # 取反
                params_filter.append(House.id.notin_(conflict_houses_id))

        elif end_date:
            # 查询
            conflict_orders = Order.query.filter(Order.begin_date >= end_date).all()

            # 遍历有冲突的订单
            conflict_houses_id = [order.house_id for order in conflict_orders]

            # 判断有冲突的房屋存在
            if conflict_houses_id:
                # 取反
                params_filter.append(House.id.notin_(conflict_houses_id))

        # 判断排序
        if "booking" == sort_key:
            houses = House.query.filter(*params_filter).order_by(House.order_count.desc())

        elif "price-inc" == sort_key:
            houses = House.query.filter(*params_filter).order_by(House.price.asc())

        elif "price-des" == sort_key:
            houses = House.query.filter(*params_filter).order_by(House.price.desc())

        else:
            houses = House.query.filter(*params_filter).order_by(House.create_time.desc())

        # 对排序后的数据分页
        houses_page = houses.paginate(page, constants.HOUSE_LIST_PAGE_CAPACITY, False)

        # 获取分页后的房屋数据， 总页数
        houses_list = houses_page.items
        total_page = houses_page.pages

        # 定义容器， 遍历
        houses_dict_list = []

        for house in houses_list:
            houses_dict_list.append(house.to_basic_dict())

    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询失败")

    # 构造响应报文
    resp = {"errno": 0, "errmsg": "OK",
            "data": {"houses": houses_dict_list, "total_page": total_page, "current_page": page}}

    # 序列化数据
    resp_json = json.dumps(resp)

    # 判断用户请求页数总页数
    if page <= total_page:
        # 构造redis_key
        redis_key = 'houses_%s_%s_%s_%s' % (area_id, start_date_str, end_date_str, sort_key)

        # 为了保证有效期， 开启事务
        pip = redis_store.pipeline()

        try:
            # 开启事务
            pip.multi()
            # 存储数据
            pip.hset(redis_key, page, resp_json)
            # 设置时间
            pip.expire(redis_key, constants.HOME_PAGE_DATA_REDIS_EXPIRES)
            # 执行事务
            pip.execute()
        except Exception as e:
            current_app.logger.error(e)

    # 返回结果
    return resp_json
