# -*- coding: utf-8 -*-
# login.py
# author: github/svjdck & github.com/icepage/AutoUpdateJdCookie & 小九九 t.me/gdot0 & zhaozg

import os
from pyppeteer import launch
import aiohttp
from urllib import request
from PIL import Image
import platform
import zipfile
import datetime
import asyncio
import random
import cv2
import numpy as np
import base64
import io
import re
# 传参获得已初始化的ddddocr实例
ocr = None
ocrDet = None

# 支持的形状类型
supported_types = [
    "三角形",
    "正方形",
    "长方形",
    "五角星",
    "六边形",
    "圆形",
    "梯形",
    "圆环",
]
# 定义了支持的每种颜色的 HSV 范围
supported_colors = {
    "紫色": ([125, 50, 50], [145, 255, 255]),
    "灰色": ([0, 0, 50], [180, 50, 255]),
    "粉色": ([160, 50, 50], [180, 255, 255]),
    "蓝色": ([100, 50, 50], [130, 255, 255]),
    "绿色": ([40, 50, 50], [80, 255, 255]),
    "橙色": ([10, 50, 50], [25, 255, 255]),
    "黄色": ([25, 50, 50], [35, 255, 255]),
    "红色": ([0, 50, 50], [10, 255, 255]),
}


async def deleteSessionDelay(workList, uid):
    s = workList.get(uid, "")
    if s:
        await asyncio.sleep(15)
        del workList[uid]
async def deleteSession(workList, uid):
    s = workList.get(uid, "")
    if s:
        del workList[uid]

async def loginPhone(chromium_path, workList, uid, headless):
    # 判断账号密码错误
    async def isWrongAccountOrPassword(page, verify=False):
        try:
            element = await page.xpath('//*[@id="app"]/div/div[5]')
            if element:
                text = await page.evaluate(
                    "(element) => element.textContent", element[0]
                )
                if text == "账号或密码不正确":
                    if verify == True:
                        return True
                    await asyncio.sleep(2)
                    return await isWrongAccountOrPassword(page, verify=True)
            return False
        except Exception as e:
            print("isWrongAccountOrPassword " + str(e))
            return False

    # 判断验证码错误
    async def isStillInSMSCodeSentPage(page):
        try:
            button = await page.querySelector('.getMsg-btn.text-btn.timer.active')
            if button:
                return False
            return await page.querySelector('#authcode')
        except Exception as e:
            print("isStillInSMSCodeSentPage " + str(e))
            return False

    # 判断验证码超时
    async def needResendSMSCode(page):
        try:
            return await page.querySelector('.getMsg-btn.text-btn.timer.active');
        except Exception as e:
            print("needResendSMSCode " + str(e))
            return False

    async def isSendSMSDirectly(page):
        try:
            title = await page.title()
            if title in ['手机语音验证', '手机短信验证']:
                print('需要' + title)
                return True  
            return False
        except Exception as e:
            print("isSendSMSDirectly " + str(e))
            return False

    usernum = workList[uid].account
    
    print(f"正在登录 {usernum} 的手机号")

    browser = await launch(
        {
            "executablePath": chromium_path,
            "headless": headless,
            "args": (
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
            ),
        }
    )
    try:
        page = await browser.newPage()
        await page.setViewport({"width": 360, "height": 640})
        await page.goto(
            "https://plogin.m.jd.com/login/login"
        )
        await typephoneuser(page, usernum)

        IN_SMS_TIMES = 0
        start_time = datetime.datetime.now()
        sms_sent = False
        while True:
            now_time = datetime.datetime.now()
            print("循环检测中...")
            if (now_time - start_time).total_seconds() > 70:
                print("进入超时分支")
                workList[uid].status = "error"
                workList[uid].msg = "登录超时"
                break

            elif await page.J("#searchWrapper"):
                print("进入成功获取cookie分支")
                workList[uid].cookie = await getCookie(page)
                workList[uid].status = "pass"
                break

            elif await page.xpath('//*[@id="captcha_modal"]'):
                print("进入安全验证分支")
                if await page.xpath('//*[@id="small_img"]'):
                    print("进入过滑块分支")

                    workList[uid].status = "pending"
                    workList[uid].msg = "正在过滑块检测"
                    await verification(page)
                    await page.waitFor(2000)
                elif await page.xpath('//*[@id="captcha_modal"]/div/div[3]/button'):
                    print("进入点形状、颜色验证分支")

                    workList[uid].status = "pending"
                    workList[uid].msg = "正在过形状、颜色检测"
                    if await verification_shape(page) == "notSupport":
                        return "notSupport"
                    await page.waitFor(2000)
                continue
            elif await page.querySelector('.dialog'):
                print("进入弹出对话框分支")
                workList[uid].status = "error"
                workList[uid].msg = "账号异常，自行检查"
                break
            if False == sms_sent:
                button = await page.querySelector('.getMsg-btn.text-btn.timer.active')
                if button is None:
                    print("进入直接发短信分支")
                    if not workList[uid].isAuto:
                        workList[uid].status = "SMS"
                        workList[uid].msg = "需要短信验证"
                        await typePhoneSMScode(page, workList, uid)
                        sms_sent = True

                    else:
                        workList[uid].status = "error"
                        workList[uid].msg = "自动续期时不能使用短信验证"
                        print("自动续期时不能使用短信验证")
                        break
            else:
                if await isStillInSMSCodeSentPage(page):
                    print("进入验证码错误分支")
                    IN_SMS_TIMES += 1
                    if IN_SMS_TIMES % 3 == 0:
                        workList[uid].SMS_CODE = None
                        workList[uid].status = "wrongSMS"
                        workList[uid].msg = "短信验证码错误，请重新输入"
                        await typePhoneSMScode(page, workList, uid)

                elif await needResendSMSCode(page):
                    print("进入验证码超时分支")
                    workList[uid].status = "error"
                    workList[uid].msg = "验证码超时，请重新开始"
                    break

            await asyncio.sleep(1)
    except Exception as e:
        workList[uid].msg = "服务器异常退出"
        workList[uid].status = "error"
        print("异常退出")
        print(e)
        await browser.close()
        await deleteSessionDelay(workList, uid)
        raise e

    print("任务完成退出")
    await browser.close()
    return
async def loginPassword(chromium_path, workList, uid, headless):
    # 判断账号密码错误
    async def isWrongAccountOrPassword(page, verify=False):
        try:
            element = await page.xpath('//*[@id="app"]/div/div[5]')
            if element:
                text = await page.evaluate(
                    "(element) => element.textContent", element[0]
                )
                if text == "账号或密码不正确":
                    if verify == True:
                        return True
                    await asyncio.sleep(2)
                    return await isWrongAccountOrPassword(page, verify=True)
            return False
        except Exception as e:
            print("isWrongAccountOrPassword " + str(e))
            return False

    # 判断验证码超时
    async def isStillInSMSCodeSentPage(page):
        try:
            if await page.xpath('//*[@id="header"]/span[2]'):
                element = await page.xpath('//*[@id="header"]/span[2]')
                if element:
                    text = await page.evaluate(
                        "(element) => element.textContent", element[0]
                    )
                    if text == "手机短信验证":
                        return True
            return False
        except Exception as e:
            print("isStillInSMSCodeSentPage " + str(e))
            return False

    # 判断验证码错误
    async def needResendSMSCode(page):
        try:
            if await page.xpath('//*[@id="app"]/div/div[2]/div[2]/button'):
                element = await page.xpath('//*[@id="app"]/div/div[2]/div[2]/button')
                if element:
                    text = await page.evaluate(
                        "(element) => element.textContent", element[0]
                    )
                    if text == "获取验证码":
                        return True
            return False
        except Exception as e:
            print("needResendSMSCode " + str(e))
            return False

    async def isSendSMSDirectly(page):
        try:
            title = await page.title()
            if title in ['手机语音验证', '手机短信验证']:
                print('需要' + title)
                return True  
            return False
        except Exception as e:
            print("isSendSMSDirectly " + str(e))
            return False

    usernum = workList[uid].account
    passwd = workList[uid].password
    sms_sent = False
    print(f"正在登录 {usernum} 的账号")

    browser = await launch(
        {
            "executablePath": chromium_path,
            "headless": headless,
            "args": (
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
            ),
        }
    )
    try:
        page = await browser.newPage()
        await page.setViewport({"width": 360, "height": 640})
        await page.goto(
            "https://plogin.m.jd.com/login/login"
        )
        await typeuser(page, usernum, passwd)

        IN_SMS_TIMES = 0
        start_time = datetime.datetime.now()

        while True:
            now_time = datetime.datetime.now()
            print("循环检测中...")
            if (now_time - start_time).total_seconds() > 70:
                print("进入超时分支")
                workList[uid].status = "error"
                workList[uid].msg = "登录超时"
                break

            elif await page.J("#searchWrapper"):
                print("进入成功获取cookie分支")
                workList[uid].cookie = await getCookie(page)
                workList[uid].status = "pass"
                break

            elif await isWrongAccountOrPassword(page):
                print("进入账号密码不正确分支")

                workList[uid].status = "error"
                workList[uid].msg = "账号或密码不正确"
                break
            elif await page.xpath('//*[@id="captcha_modal"]'):
                print("进入安全验证分支")
                if await page.xpath('//*[@id="small_img"]'):
                    print("进入过滑块分支")

                    workList[uid].status = "pending"
                    workList[uid].msg = "正在过滑块检测"
                    await verification(page)
                    await page.waitFor(3000)
                elif await page.xpath('//*[@id="captcha_modal"]/div/div[3]/button'):
                    print("进入点形状、颜色验证分支")
                    
                    workList[uid].status = "pending"
                    workList[uid].msg = "正在过形状、颜色检测"
                    if await verification_shape(page) == "notSupport":
                        print("即将重启浏览器重试")
                        await browser.close()
                        return "notSupport"
                    await page.waitFor(3000)
            elif await page.querySelector('.dialog'):
                print("进入弹出对话框分支")
                workList[uid].status = "error"
                workList[uid].msg = "账号异常，自行检查"
                break
            if not sms_sent:

                if await page.J(".sub-title"):
                    print("进入选择短信验证分支")
                    if not workList[uid].isAuto:
                        workList[uid].status = "SMS"
                        workList[uid].msg = "需要短信验证"

                        if await sendSMS(page) == "notSupport":
                            print("即将重启浏览器重试")
                            await browser.close()
                            return "notSupport"
                        await page.waitFor(3000)
                        await typeSMScode(page, workList, uid)
                        sms_sent = True

                    else:
                        workList[uid].status = "error"
                        workList[uid].msg = "自动续期时不能使用短信验证"
                        print("自动续期时不能使用短信验证")
                        break
                elif await isSendSMSDirectly(page):
                    print("进入直接发短信分支")

                    if not workList[uid].isAuto:
                        workList[uid].status = "SMS"
                        workList[uid].msg = "需要短信验证"
                        if await sendSMSDirectly(page) == "notSupport":
                            print("即将重启浏览器重试")
                            await browser.close()
                            return "notSupport"
                        await page.waitFor(3000)
                        await typeSMScode(page, workList, uid)
                        sms_sent = True

                    else:
                        workList[uid].status = "error"
                        workList[uid].msg = "自动续期时不能使用短信验证"
                        print("自动续期时不能使用短信验证")
                        break
            else:
                if await isStillInSMSCodeSentPage(page):
                    print("进入验证码错误分支")
                    IN_SMS_TIMES += 1
                    if IN_SMS_TIMES % 3 == 0:
                        workList[uid].SMS_CODE = None
                        workList[uid].status = "wrongSMS"
                        workList[uid].msg = "短信验证码错误，请重新输入"
                        await typeSMScode(page, workList, uid)

                elif await needResendSMSCode(page):
                    print("进入验证码超时分支")
                    workList[uid].status = "error"
                    workList[uid].msg = "验证码超时，请重新开始"
                    break

            await asyncio.sleep(1)
    except Exception as e:
        print("异常退出")
        print(e)
        await browser.close()
        await deleteSessionDelay(workList, uid)
        raise e
        
    print("任务完成退出")

    await browser.close()
    return

async def typephoneuser(page, usernum):
    await page.waitFor(random.randint(200, 500))
    tel_input = await page.waitForSelector('input[type="tel"]')
    await tel_input.click()
    await tel_input.type(usernum)
    #await page.type(
    #    "input[type='tel']", usernum, {"delay": random.randint(50,100)}
    #)
    await page.waitFor(random.randint(200, 500))
    await page.click(".policy_tip-checkbox")
    await page.waitFor(random.randint(200, 500))
    await page.click(".getMsg-btn.text-btn.timer")
    await page.waitFor(random.randint(500, 1000))
async def typeuser(page, usernum, passwd):
    print("开始输入账号密码")
    await page.waitForSelector(".J_ping.planBLogin")
    await page.click(".J_ping.planBLogin")
    await page.type(
        "#username", usernum, {"delay": random.randint(10, 20)}
    )
    await page.type(
        "#pwd", passwd, {"delay": random.randint(10, 20)}
    )
    await page.waitFor(random.randint(200, 500))
    await page.click(".policy_tip-checkbox")
    await page.waitFor(random.randint(200, 500))
    await page.click(".btn.J_ping.btn-active")
    await page.waitFor(random.randint(500, 1000))


async def sendSMSDirectly(page):
    async def preSendSMS(page):
        await page.waitForXPath(
            '//*[@id="app"]/div/div[2]/div[2]/button'
        )
        await page.waitFor(random.randint(1, 3) * 1000)
        elements = await page.xpath(
            '//*[@id="app"]/div/div[2]/div[2]/button'
        )
        await elements[0].click()
        await page.waitFor(3000)

    await preSendSMS(page)
    print("开始发送验证码")

    try:
        while True:
            if await page.xpath('//*[@id="captcha_modal"]/div/div[3]/div'):
                await verification(page)

            elif await page.xpath('//*[@id="captcha_modal"]/div/div[3]/button'):
                if await verification_shape(page) == "notSupport":
                    return "notSupport"

            else:
                break

            await page.waitFor(3000)

    except Exception as e:
        raise e


async def sendSMS(page):
    async def preSendSMS(page):
        print("进行发送验证码前置操作")
        await page.waitForXPath(
            '//*[@id="app"]/div/div[2]/div[2]/span/a'
        )
        await page.waitFor(random.randint(1, 3) * 1000)
        elements = await page.xpath(
            '//*[@id="app"]/div/div[2]/div[2]/span/a'
        )
        await elements[0].click()
        await page.waitForXPath(
            '//*[@id="app"]/div/div[2]/div[2]/button'
        )
        await page.waitFor(random.randint(1, 3) * 1000)
        elements = await page.xpath(
            '//*[@id="app"]/div/div[2]/div[2]/button'
        )
        await elements[0].click()
        await page.waitFor(3000)

    await preSendSMS(page)
    print("开始发送验证码")

    try:
        while True:
            if await page.xpath('//*[@id="captcha_modal"]/div/div[3]/div'):
                await verification(page)

            elif await page.xpath('//*[@id="captcha_modal"]/div/div[3]/button'):
                if await verification_shape(page) == "notSupport":
                    return "notSupport"

            else:
                break

            await page.waitFor(3000)

    except Exception as e:
        raise e

async def typePhoneSMScode(page, workList, uid):
    print("开始输入验证码")

    async def get_verification_code(workList, uid):
        print("开始从全局变量获取验证码")
        retry = 60
        while not workList[uid].SMS_CODE and not retry < 0:
            await asyncio.sleep(1)
            retry -= 1
        if retry < 0:
            workList[uid].status = "error"
            workList[uid].msg = "输入短信验证码超时"
            return

        workList[uid].status = "pending"
        return workList[uid].SMS_CODE
    code = await get_verification_code(workList, uid)
    if not code:
        return

    workList[uid].status = "pending"
    workList[uid].msg = "正在通过短信验证"
    authcode_input = await page.waitForSelector('#authcode')
    await authcode_input.type(code)
    await page.waitFor(random.randint(100,300))
    button = await page.waitForSelector('.btn.J_ping')  
    await button.click()
    await page.waitFor(random.randint(2, 3) * 1000)



async def typeSMScode(page, workList, uid):
    print("开始输入验证码")

    async def get_verification_code(workList, uid):
        print("开始从全局变量获取验证码")
        retry = 60
        while not workList[uid].SMS_CODE and not retry < 0:
            await asyncio.sleep(1)
            retry -= 1
        if retry < 0:
            workList[uid].status = "error"
            workList[uid].msg = "输入短信验证码超时"
            return

        workList[uid].status = "pending"
        return workList[uid].SMS_CODE
    await page.waitForXPath('//*[@id="app"]/div/div[2]/div[2]/div/input')
    code = await get_verification_code(workList, uid)
    if not code:
        return

    workList[uid].status = "pending"
    workList[uid].msg = "正在通过短信验证"
    input_elements = await page.xpath('//*[@id="app"]/div/div[2]/div[2]/div/input')

    try:
        if input_elements:
            input_value = await input_elements[0].getProperty("value")
            if input_value:
                print("清除验证码输入框中已有的验证码")
                await page.evaluate(
                    '(element) => element.value = ""', input_elements[0]
                )

    except Exception as e:
        print("typeSMScode" + str(e))

    await input_elements[0].type(code)
    await page.waitForXPath('//*[@id="app"]/div/div[2]/a[1]')
    await page.waitFor(random.randint(1, 3) * 1000)
    elements = await page.xpath('//*[@id="app"]/div/div[2]/a[1]')
    await elements[0].click()
    await page.waitFor(random.randint(2, 3) * 1000)


async def verification(page):
    print("开始过滑块")

    async def get_distance():
        img = cv2.imread("image.png", 0)
        template = cv2.imread("template.png", 0)
        img = cv2.GaussianBlur(img, (5, 5), 0)
        template = cv2.GaussianBlur(template, (5, 5), 0)
        bg_edge = cv2.Canny(img, 100, 200)
        cut_edge = cv2.Canny(template, 100, 200)
        img = cv2.cvtColor(bg_edge, cv2.COLOR_GRAY2RGB)
        template = cv2.cvtColor(cut_edge, cv2.COLOR_GRAY2RGB)
        res = cv2.matchTemplate(
            img, template, cv2.TM_CCOEFF_NORMED
        )
        value = cv2.minMaxLoc(res)[3][0]
        distance = (
            value + 10
        )
        return distance

    await page.waitForSelector("#cpc_img")
    image_src = await page.Jeval(
        "#cpc_img", 'el => el.getAttribute("src")'
    )
    request.urlretrieve(image_src, "image.png")
    width = await page.evaluate(
        '() => { return document.getElementById("cpc_img").clientWidth; }'
    )
    height = await page.evaluate(
        '() => { return document.getElementById("cpc_img").clientHeight; }'
    )
    image = Image.open("image.png")
    resized_image = image.resize((width, height))
    resized_image.save("image.png")
    template_src = await page.Jeval(
        "#small_img", 'el => el.getAttribute("src")'
    )
    request.urlretrieve(template_src, "template.png")
    width = await page.evaluate(
        '() => { return document.getElementById("small_img").clientWidth; }'
    )
    height = await page.evaluate(
        '() => { return document.getElementById("small_img").clientHeight; }'
    )
    image = Image.open("template.png")
    resized_image = image.resize((width, height))
    resized_image.save("template.png")
    await page.waitFor(100)
    el = await page.querySelector(
        "#captcha_modal > div > div.captcha_footer > div > img"
    )
    box = await el.boundingBox()
    distance = await get_distance()
    await page.mouse.move(box["x"] + 10, box["y"] + 10)
    await page.mouse.down()
    await page.mouse.move(
        box["x"] + distance + random.uniform(3, 15), box["y"], {"steps": 10}
    )
    await page.waitFor(
        random.randint(100, 500)
    )
    await page.mouse.move(
        box["x"] + distance, box["y"], {"steps": 10}
    )
    await page.mouse.up()
    print("过滑块结束")


async def verification_shape(page):
    print("开始过颜色、形状验证")

    def get_shape_location_by_type(img_path, type: str):
        def sort_rectangle_vertices(vertices):
            vertices = sorted(vertices, key=lambda x: x[1])
            top_left, top_right = sorted(vertices[:2], key=lambda x: x[0])
            bottom_left, bottom_right = sorted(vertices[2:], key=lambda x: x[0])
            return [top_left, top_right, bottom_right, bottom_left]

        def is_trapezoid(vertices):
            top_width = abs(vertices[1][0] - vertices[0][0])
            bottom_width = abs(vertices[2][0] - vertices[3][0])
            return top_width < bottom_width

        img = cv2.imread(img_path)
        imgGray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        imgBlur = cv2.GaussianBlur(imgGray, (5, 5), 1)
        imgCanny = cv2.Canny(imgBlur, 60, 60)
        contours, hierarchy = cv2.findContours(
            imgCanny, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        for obj in contours:
            perimeter = cv2.arcLength(obj, True)
            approx = cv2.approxPolyDP(obj, 0.02 * perimeter, True)
            CornerNum = len(approx)
            x, y, w, h = cv2.boundingRect(approx)

            if CornerNum == 3:
                obj_type = "三角形"
            elif CornerNum == 4:
                if w == h:
                    obj_type = "正方形"
                else:
                    approx = sort_rectangle_vertices([vertex[0] for vertex in approx])
                    if is_trapezoid(approx):
                        obj_type = "梯形"
                    else:
                        obj_type = "长方形"
            elif CornerNum == 6:
                obj_type = "六边形"
            elif CornerNum == 8:
                obj_type = "圆形"
            elif CornerNum == 20:
                obj_type = "五角星"
            else:
                obj_type = "未知"

            if obj_type == type:
                center_x, center_y = x + w // 2, y + h // 2
                return center_x, center_y

        return None, None

    def get_shape_location_by_color(img_path, target_color):
        image = cv2.imread(img_path)
        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

        lower, upper = supported_colors[target_color]
        lower = np.array(lower, dtype="uint8")
        upper = np.array(upper, dtype="uint8")

        mask = cv2.inRange(hsv_image, lower, upper)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            if cv2.contourArea(contour) > 100:
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    return cX, cY

        return None, None

    def get_word(ocr, img_path):
        image_bytes = open(img_path, "rb").read()
        result = ocr.classification(image_bytes, png_fix=True)
        return result

    def rgba2rgb(rgb_image_path, rgba_img_path):
        rgba_image = Image.open(rgba_img_path)
        rgb_image = Image.new("RGB", rgba_image.size, (255, 255, 255))
        rgb_image.paste(rgba_image, (0, 0), rgba_image)
        rgb_image.save(rgb_image_path)

    def save_img(img_path, img_bytes):
        with Image.open(io.BytesIO(img_bytes)) as img:
            img.save(img_path)

    def get_img_bytes(img_src: str) -> bytes:
        img_base64 = re.search(r"base64,(.*)", img_src)
        if img_base64:
            base64_code = img_base64.group(1)
            img_bytes = base64.b64decode(base64_code)
            return img_bytes
        else:
            raise "image is empty"

    def get_gray_img(path):
        img = cv2.imread(path)
        gray = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY))
        gray.save("gray.png")
        return open("gray.png", "rb").read()

    # 文字点选的重试次数，超过将重启浏览器
    retry_count = 10
    for i in range(5):
        await page.waitForSelector("div.captcha_footer img")
        image_src = await page.Jeval(
            "#cpc_img", 'el => el.getAttribute("src")'
        )
        request.urlretrieve(image_src, "shape_image.png")
        width = await page.evaluate(
            '() => { return document.getElementById("cpc_img").clientWidth; }'
        )
        height = await page.evaluate(
            '() => { return document.getElementById("cpc_img").clientHeight; }'
        )
        image = Image.open("shape_image.png")
        resized_image = image.resize((width, height))
        resized_image.save("shape_image.png")

        b_image = await page.querySelector("#cpc_img")
        b_image_box = await b_image.boundingBox()
        image_top_left_x = b_image_box["x"]
        image_top_left_y = b_image_box["y"]

        word_src = await page.Jeval(
            "div.captcha_footer img", 'el => el.getAttribute("src")'
        )
        word_bytes = get_img_bytes(word_src)
        save_img("rgba_word_img.png", word_bytes)
        rgba2rgb("rgb_word_img.png", "rgba_word_img.png")
        word = get_word(ocr, "rgb_word_img.png")

        button = await page.querySelector("div.captcha_footer button.sure_btn")
        if button is None:
            button = await page.querySelector(".sure_btn")
        if button is None:
            print("未找到提交按钮")
            raise "未找到提交按钮"
        refresh_button = await page.querySelector("div.captcha_header img.jcap_refresh")
        if refresh_button is None:
            refresh_button = await page.querySelector("div.captcha_header span.jcap_refresh")
        if refresh_button is None:
            refresh_button = await page.querySelector(".jcap_refresh")


        if word.find("色") > 0:
            target_color = word.split("请选出图中")[1].split("的图形")[0]
            if target_color in supported_colors:
                print(f"正在找{target_color}")
                center_x, center_y = get_shape_location_by_color(
                    "shape_image.png", target_color
                )
                if center_x is None and center_y is None:
                    print("识别失败，刷新")
                    if refresh_button is None:
                        print("未找到刷新按钮")
                        raise "未找到刷新按钮"
                    await refresh_button.click()
                    await asyncio.sleep(random.uniform(2, 4))
                    continue
                x, y = image_top_left_x + center_x, image_top_left_y + center_y
                await page.mouse.click(x, y)
                await asyncio.sleep(random.uniform(0.5, 2))
                await button.click()
                await asyncio.sleep(random.uniform(0.3, 1))
                break
            else:
                print(f"不支持{target_color}，重试")
                if refresh_button is None:
                    print("未找到刷新按钮")
                    raise "未找到刷新按钮"
                await refresh_button.click()
                await asyncio.sleep(random.uniform(2, 4))
                break
        elif word.find("依次") > 0:
            if retry_count < 1:
                print("文字点选重试失败")
                return "notSupport"
            i = 3
            print("进入文字点选")
            print(f"文字点选第{11 - retry_count}次尝试")
            retry_count -= 1
            target_word = word.replace("\"", "")[-4:]
            print(f"点选字为： {target_word}")
            gray_img = get_gray_img("shape_image.png")
            xy_list = ocrDet.detection(gray_img)
            src_img = Image.open("shape_image.png")
            words = []
            for row in xy_list:
                [x1, y1, x2, y2] = row
                corp = src_img.crop([x1 - 7 if x1 > 7 else x1, y1 - 7 if y1 > 7 else y1, x2 + 7, y2 + 7])
                # 识别出单个字
                result_word = ocr.classification(corp, png_fix=True)
                words.append(result_word)
            result = dict(zip(words, xy_list))
            print(f"result: {result}")
            img_xy = {}
            for key, xy in result.items():
                img_xy[key] = (int((xy[0] + xy[2]) / 2), int((xy[1] + xy[3]) / 2))
            not_found = False
            click_points = {}
            for wd in target_word:
                if wd not in img_xy:
                    print(f"\"{wd}\"未找到，识别失败,刷新")
                    if refresh_button is None:
                        print("未找到刷新按钮")
                        raise "未找到刷新按钮"
                    await refresh_button.click()
                    await asyncio.sleep(random.uniform(2, 4))
                    not_found = True
                    break
                center_x, center_y = img_xy[wd]
                click_x, click_y = image_top_left_x + center_x, image_top_left_y + center_y
                click_points[wd] = [click_x, click_y]
            print(click_points)
            if os.path.exists("gray.png"):
                os.remove("gray.png")
            if not_found:
                continue
            print("文字点选识别正常")
            for wd, point in click_points.items():
                print(f"点击\"{wd}\",坐标{point[0]}:{point[1]}")
                await page.mouse.click(point[0], point[1])
                await asyncio.sleep(random.uniform(0.5, 2))
            await button.click()
            await asyncio.sleep(random.uniform(0.3, 1))
            break
        else:
            shape_type = word.split("请选出图中的")[1]
            if shape_type in supported_types:
                print(f"正在找{shape_type}")
                if shape_type == "圆环":
                    shape_type = shape_type.replace("圆环", "圆形")
                center_x, center_y = get_shape_location_by_type(
                    "shape_image.png", shape_type
                )
                if center_x is None and center_y is None:
                    print(f"识别失败,刷新")
                    if refresh_button is None:
                        print("未找到刷新按钮")
                        raise "未找到刷新按钮"
                    await refresh_button.click()
                    await asyncio.sleep(random.uniform(2, 4))
                    continue
                x, y = image_top_left_x + center_x, image_top_left_y + center_y
                await page.mouse.click(x, y)
                await asyncio.sleep(random.uniform(0.5, 2))
                await button.click()
                await asyncio.sleep(random.uniform(0.3, 1))
                break
            else:
                print(f"不支持{shape_type},刷新中......")
                if refresh_button is None:
                    print("未找到刷新按钮")
                    raise "未找到刷新按钮"
                await refresh_button.click()
                await asyncio.sleep(random.uniform(2, 4))
                continue
    print("过图形结束")


async def getCookie(page):
    cookies = await page.cookies()
    pt_key = ""
    pt_pin = ""
    for cookie in cookies:
        if cookie["name"] == "pt_key":
            pt_key = cookie["value"]
        elif cookie["name"] == "pt_pin":
            pt_pin = cookie["value"]
    ck = f"pt_key={pt_key};pt_pin={pt_pin};"
    print(f"登录成功 {ck}")
    return ck


async def download_file(url, file_path):
    timeout = aiohttp.ClientTimeout(total=60000)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            with open(file_path, "wb") as file:
                file_size = int(response.headers.get("Content-Length", 0))
                downloaded_size = 0
                chunk_size = 1024
                while True:
                    chunk = await response.content.read(chunk_size)
                    if not chunk:
                        break
                    file.write(chunk)
                    downloaded_size += len(chunk)
                    progress = (downloaded_size / file_size) * 100
                    print(f"已下载{progress:.2f}%...", end="\r")
    print("下载完成，进行解压安装....")


async def main(workList, uid, oocr, oocrDet):
    global ocr, ocrDet
    ocr = oocr
    ocrDet = oocrDet

    async def init_chrome():
        if platform.system() == "Windows":
            chrome_dir = os.path.join(
                os.environ["USERPROFILE"],
                "AppData",
                "Local",
                "pyppeteer",
                "pyppeteer",
                "local-chromium",
                "588429",
                "chrome-win32",
            )
            chrome_exe = os.path.join(chrome_dir, "chrome.exe")
            chmod_dir = os.path.join(
                os.environ["USERPROFILE"],
                "AppData",
                "Local",
                "pyppeteer",
                "pyppeteer",
                "local-chromium",
                "588429",
                "chrome-win32",
                "chrome-win32",
            )
            if os.path.exists(chrome_exe):
                return chrome_exe
            else:
                print("貌似第一次使用，未找到chrome，正在下载chrome浏览器....")

                chromeurl = "https://mirrors.huaweicloud.com/chromium-browser-snapshots/Win_x64/588429/chrome-win32.zip"
                target_file = "chrome-win.zip"
                await download_file(chromeurl, target_file)
                with zipfile.ZipFile(target_file, "r") as zip_ref:
                    zip_ref.extractall(chrome_dir)
                os.remove(target_file)
                for item in os.listdir(chmod_dir):
                    source_item = os.path.join(chmod_dir, item)
                    destination_item = os.path.join(chrome_dir, item)
                    os.rename(source_item, destination_item)
                print("解压安装完成")
                await asyncio.sleep(1)
                return chrome_exe

        elif platform.system() == "Linux":
            chrome_path = os.path.expanduser(
                "~/.local/share/pyppeteer/local-chromium/1181205/chrome-linux/chrome"
            )
            download_path = os.path.expanduser(
                "~/.local/share/pyppeteer/local-chromium/1181205/"
            )
            if os.path.isfile(chrome_path):
                return chrome_path
            else:
                print("貌似第一次使用，未找到chrome，正在下载chrome浏览器....")
                print("文件位于github，请耐心等待，如遇到网络问题可到项目地址手动下载")
                download_url = "https://mirrors.huaweicloud.com/chromium-browser-snapshots/Linux_x64/884014/chrome-linux.zip"
                if 'arm' in platform.machine():
                    download_url = "https://playwright.azureedge.net/builds/chromium/1088/chromium-linux-arm64.zip";
                if not os.path.exists(download_path):
                    os.makedirs(download_path, exist_ok=True)
                target_file = os.path.join(
                    download_path, "chrome-linux.zip"
                )
                await download_file(download_url, target_file)
                with zipfile.ZipFile(target_file, "r") as zip_ref:
                    zip_ref.extractall(download_path)
                os.remove(target_file)
                os.chmod(chrome_path, 0o755)
                return chrome_path
        elif platform.system() == "Darwin":
            return "mac"
        else:
            return "unknown"
    print("判断初始化浏览器")
    chromium_path = await init_chrome()
    headless = 'new'
    #headless = False
    print("选择登录")
    
    try_time = 1
    while True:
        if workList[uid].type == "phone":
            print("选择手机号登录")
            result = await loginPhone(chromium_path, workList, uid, headless)
        elif workList[uid].type == "password":
	        print("选择密码登录")
	        result = await loginPassword(chromium_path, workList, uid, headless)
        if result != "notSupport" or try_time > 5:
            break
        await asyncio.sleep(random.uniform(2, 4))
        print(f"进行第{try_time}次重试")
        try_time += 1
    if os.path.exists("image.png"):
        os.remove("image.png")
    if os.path.exists("template.png"):
        os.remove("template.png")
    if os.path.exists("shape_image.png"):
        os.remove("shape_image.png")
    if os.path.exists("rgba_word_img.png"):
        os.remove("rgba_word_img.png")
    if os.path.exists("rgb_word_img.png"):
        os.remove("rgb_word_img.png")
    await deleteSessionDelay(workList, uid)
    print("登录完成")
    await asyncio.sleep(10)
