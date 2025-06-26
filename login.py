# -*- coding: utf-8 -*-
# login.py
# author: github/svjdck & github.com/icepage/AutoUpdateJdCookie & 小九九 t.me/gdot0

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
import logging
#from fake_useragent import UserAgent

# 传参获得已初始化的ddddocr实例
ocr = None
ocrDet = None

logger = logging.getLogger("login")
simple_format = "[%(asctime)s][%(levelname)s][%(filename)s:%(lineno)d] %(message)s"
logging.basicConfig(level=logging.INFO, format=simple_format, datefmt="%Y-%m-%d %H:%M:%S %z")

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


async def deleteSession(workList, uid):
    s = workList.get(uid, "")
    if s:
        await asyncio.sleep(15)
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
            logger.info("isWrongAccountOrPassword " + str(e))
            return False

    # 判断验证码错误
    async def isStillInSMSCodeSentPage(page):
        try:
            if not await page.querySelector('.getMsg-btn.text-btn.timer.active') and await page.querySelector('#authcode'):
                return True
            return False
        except Exception as e:
            logger.info("isStillInSMSCodeSentPage " + str(e))
            return False

    # 判断验证码超时
    async def needResendSMSCode(page):
        try:
            if await page.querySelector('.getMsg-btn.text-btn.timer.active'):
                return True
            return False
        except Exception as e:
            logger.info("needResendSMSCode " + str(e))
            return False

    async def isSendSMSDirectly(page):
        try:
            title = await page.title()
            if title in ['手机语音验证', '手机短信验证']:
                logger.info('需要' + title)
                return True  
            return False
        except Exception as e:
            logger.info("isSendSMSDirectly " + str(e))
            return False

    usernum = workList[uid].account
    
    logger.info(f"正在登录 {usernum} 的手机号")

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
    page = await browser.newPage()
    await page.setUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    await page.setViewport({"width": 360, "height": 640})
    await page.goto(
        "https://plogin.m.jd.com/login/login"
    )
    await typephoneuser(page, usernum)

    IN_SMS_TIMES = 0
    start_time = datetime.datetime.now()
    sms_sent = False
    while True:
        try:
            now_time = datetime.datetime.now()
            logger.info("循环检测中...")
            if (now_time - start_time).total_seconds() > 70:
                logger.info("进入超时分支")
                workList[uid].status = "error"
                workList[uid].msg = "登录超时"
                break

            elif await page.J("#searchWrapper"):
                logger.info("进入成功获取cookie分支")
                workList[uid].cookie = await getCookie(page)
                workList[uid].status = "pass"
                break

            elif await page.xpath('//*[@id="captcha_modal"]'):
                logger.info("进入安全验证分支")
                if await page.xpath('//*[@id="slot_img"]'):
                    logger.info("进入过滑块分支")

                    workList[uid].status = "pending"
                    workList[uid].msg = "正在过滑块检测"
                    await verification(page)
                    await page.waitFor(2000)
                elif await page.xpath('//*[@id="captcha_modal"]/div/div[4]/button'):
                    logger.info("进入点形状、颜色验证分支")

                    workList[uid].status = "pending"
                    workList[uid].msg = "正在过形状、颜色检测"
                    if await verification_shape(page) == "notSupport":
                        return "notSupport"
                    await page.waitFor(2000)
                continue
            elif await page.querySelector('.dialog'):
                logger.info("进入弹出对话框分支")
                workList[uid].status = "error"
                workList[uid].msg = "账号异常，自行检查"
                break
            if False == sms_sent:
                button = await page.querySelector('.getMsg-btn.text-btn.timer.active')
                if button is None:
                    logger.info("进入直接发短信分支")
                    if not workList[uid].isAuto:
                        workList[uid].status = "SMS"
                        workList[uid].msg = "需要短信验证"
                        await typePhoneSMScode(page, workList, uid)
                        sms_sent = True

                    else:
                        workList[uid].status = "error"
                        workList[uid].msg = "自动续期时不能使用短信验证"
                        logger.info("自动续期时不能使用短信验证")
                        break
            else:
                if await isStillInSMSCodeSentPage(page):
                    logger.info("进入验证码错误分支")
                    IN_SMS_TIMES += 1
                    if IN_SMS_TIMES % 3 == 0:
                        workList[uid].SMS_CODE = None
                        workList[uid].status = "wrongSMS"
                        workList[uid].msg = "短信验证码错误，请重新输入"
                        await typePhoneSMScode(page, workList, uid)

                elif await needResendSMSCode(page):
                    logger.info("进入验证码超时分支")
                    workList[uid].status = "error"
                    workList[uid].msg = "验证码超时，请重新开始"
                    break

            await asyncio.sleep(1)
        except Exception as e:
            logger.info("异常退出")
            logger.error(e)
            await browser.close()
            await deleteSession(workList, uid)
            workList[uid].status = "error"
            workList[uid].msg = "异常退出"
            raise e

    logger.info("任务完成退出")

    logger.info("任务完成退出")
    logger.info("开始删除缓存文件......")
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
    logger.info("缓存文件已删除！")
    logger.info("开始关闭浏览器....")
    await browser.close()
    logger.info("浏览器已关闭！")
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
            logger.info("isWrongAccountOrPassword " + str(e))
            return False

        # 判断验证码错误
    async def isStillInSMSCodeSentPage(page):
        try:
            if not await page.querySelector('.getMsg-btn.timer.active') and await page.querySelector('.acc-input.msgCode'):
                return True
            return False
        except Exception as e:
            logger.info("isStillInSMSCodeSentPage " + str(e))
            return False

    # 判断验证码超时
    async def needResendSMSCode(page):
        try:
            if await page.querySelector('.getMsg-btn.timer.active'):
                return True
            return False
        except Exception as e:
            logger.info("needResendSMSCode " + str(e))
            return False

    async def isSendSMSDirectly(page):
        try:
            title = await page.title()
            if title in ['手机语音验证', '手机短信验证']:
                logger.info('需要' + title)
                return True
            return False
        except Exception as e:
            logger.info("isSendSMSDirectly " + str(e))
            return False

    usernum = workList[uid].account
    passwd = workList[uid].password
    sms_sent = False
    logger.info(f"正在登录 {usernum} 的账号")

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
    page = await browser.newPage()
    await page.setUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    #user_agent = await page.evaluate("navigator.userAgent")
    #print(f"User-Agent: {user_agent}")
    await page.setViewport({"width": 360, "height": 640})
    await page.goto(
        "https://plogin.m.jd.com/login/login?appid=300&returnurl=https%3A%2F%2Fm.jd.com%2F&source=wq_passport"
    )
    await typeuser(page, usernum, passwd)

    IN_SMS_TIMES = 0
    start_time = datetime.datetime.now()

    while True:
        try:
            now_time = datetime.datetime.now()
            logger.info("循环检测中...")
            if (now_time - start_time).total_seconds() > 120:
                logger.info("进入超时分支")
                workList[uid].status = "error"
                workList[uid].msg = "登录超时"
                logger.info("超时了，正在保存当前页面信息......")
                dateTime = datetime.datetime.now().strftime('%Y%m%d %H_%M_%S.%f')
                logger.info(f"页面截图保存到： {usernum}-screenshot-{dateTime}.png")
                await page.screenshot({'path': f"{usernum}-screenshot-{dateTime}.png"})
                logger.info(f"页面HTML保存到： {usernum}-html-{dateTime}.html")
                content = await page.content()
                with open(f"{usernum}-html-{dateTime}.html", 'w', encoding='utf-8') as f:
                    f.write(content)
                break

            elif await page.J("#searchWrapper"):
                logger.info("进入成功获取cookie分支")
                workList[uid].cookie = await getCookie(page)
                workList[uid].status = "pass"
                break

            elif await isWrongAccountOrPassword(page):
                logger.info("进入账号密码不正确分支")

                workList[uid].status = "error"
                workList[uid].msg = "账号或密码不正确"
                break

            elif await page.xpath('//*[@id="captcha_modal"]'):
                logger.info("进入安全验证分支")
                if await page.xpath('//*[@id="slot_img"]'):
                    logger.info("进入过滑块分支")

                    workList[uid].status = "pending"
                    workList[uid].msg = "正在过滑块检测"
                    await verification(page)
                    await page.waitFor(3000)

                elif await page.xpath('//*[@id="captcha_modal"]/div/div[4]/button'):
                    logger.info("进入点形状、颜色验证分支")
                    workList[uid].status = "pending"
                    workList[uid].msg = "正在过形状、颜色检测"
                    if await verification_shape(page) == "notSupport":
                        logger.info("即将重启浏览器重试")
                        await browser.close()
                        return "notSupport"
                    await page.waitFor(3000)

                elif await page.J('.drag-content'):
                    logger.info("进入旋转图片分支")
                    logger.info("正在保存当前页面信息......")
                    dateTime = datetime.datetime.now().strftime('%Y%m%d %H_%M_%S.%f')
                    logger.info(f"页面截图保存到： drag_{usernum}-screenshot-{dateTime}.png")
                    await page.screenshot({'path': f"drag_{usernum}-screenshot-{dateTime}.png"})
                    logger.info("即将重启浏览器重试")
                    await browser.close()
                    return "notSupport"

            elif await page.J('.alert-body #alertMsg'):
                logger.info("进入弹框分支")
                element = await page.J('.alert-body #alertMsg')
                if element:
                    alertMsg = await page.evaluate(
                        "(element) => element.textContent", element
                    )
                    logger.info(f"弹框内容为: {alertMsg}")
                    if alertMsg == "发送短信验证码过于频繁，请稍后再试":
                        workList[uid].status = "error"
                        workList[uid].msg = "发送短信验证码过于频繁，请稍后再试"
                        break
                    elif alertMsg == "身份证号输入错误,若包含字母X,请输入大写字母":
                        logger.info("进入身份证号错误分支")
                        workList[uid].ID_CARD = None
                        workList[uid].status = "wrongIDCard"
                        workList[uid].msg = "身份证号输入错误,若包含字母X,请输入大写字母"
                        await page.click('.alert-sure')
                        await page.waitFor(random.randint(100, 2000))
                        input_elements = await page.JJ('.input-container.id-wrap > div')
                        await input_elements[5].click()
                        for i in range(6):
                            await page.keyboard.press('Backspace')
                            await page.waitFor(random.randint(100, 2000))
                        await page.waitFor(3000)
                        await typeIDCard(page, workList, uid)
                        if workList[uid].status == "error":
                            logger.info("输入身份证超时")
                            break
                    elif alertMsg == "您已超过当日请求上限，请明天再试":
                        workList[uid].status = "error"
                        workList[uid].msg = "您已超过当日请求上限，请明天再试"
                        break
                    elif alertMsg == "验证码错误多次，请重新获取":
                        workList[uid].status = "error"
                        workList[uid].msg = "验证码错误多次，请重新获取"
                        break


            # 需要身份证验证
            if await page.J(".sub-title") and await page.J('.icon-default.icon-userid'):
                logger.info("进入身份证号验证分支")
                if not workList[uid].isAuto:
                    await page.click(".icon-default.icon-userid")
                    workList[uid].status = "IDCard"
                    workList[uid].msg = "存在安全风险，请输入身份证号码的前两位和后四位验证身份"
                    await page.waitFor(3000)
                    await typeIDCard(page, workList, uid)
                    if workList[uid].status == "error":
                        logger.info("输入身份证超时")
                        break
                else:
                    workList[uid].status = "error"
                    workList[uid].msg = "自动续期时不能使用身份证号验证"
                    logger.info("自动续期时不能使用身份证号验证")
                    break

            if not sms_sent:
                if await page.J(".sub-title") and not await page.J('.icon-default.icon-userid'):
                    logger.info("进入选择短信验证分支")
                    if not workList[uid].isAuto:
                        workList[uid].status = "SMS"
                        workList[uid].msg = "需要短信验证"

                        if await sendSMS(page) == "notSupport":
                            logger.info("即将重启浏览器重试")
                            await browser.close()
                            return "notSupport"
                        await page.waitFor(3000)
                        await typeSMScode(page, workList, uid)
                        sms_sent = True

                    else:
                        workList[uid].status = "error"
                        workList[uid].msg = "自动续期时不能使用短信验证"
                        logger.info("自动续期时不能使用短信验证")
                        break
                elif await isSendSMSDirectly(page):
                    logger.info("进入直接发短信分支")

                    if not workList[uid].isAuto:
                        workList[uid].status = "SMS"
                        workList[uid].msg = "需要短信验证"
                        if await sendSMSDirectly(page) == "notSupport":
                            logger.info("即将重启浏览器重试")
                            await browser.close()
                            return "notSupport"
                        await page.waitFor(3000)
                        await typeSMScode(page, workList, uid)
                        sms_sent = True

                    else:
                        workList[uid].status = "error"
                        workList[uid].msg = "自动续期时不能使用短信验证"
                        logger.info("自动续期时不能使用短信验证")
                        break
            else:
                if await isStillInSMSCodeSentPage(page):
                    logger.info("进入验证码错误分支")
                    IN_SMS_TIMES += 1
                    if IN_SMS_TIMES % 3 == 0:
                        workList[uid].SMS_CODE = None
                        workList[uid].status = "wrongSMS"
                        workList[uid].msg = "短信验证码错误，请重新输入"
                        await typeSMScode(page, workList, uid)

                elif await needResendSMSCode(page):
                    logger.info("进入验证码超时分支")
                    workList[uid].status = "error"
                    workList[uid].msg = "验证码超时，请重新开始"
                    break

            await asyncio.sleep(1)
        except Exception as e:
            logger.info("异常退出")
            logger.error(e)
            logger.info("异常退出，正在保存当前页面信息......")
            dateTime = datetime.datetime.now().strftime('%Y%m%d %H_%M_%S.%f')
            logger.info(f"页面截图保存到： error_{usernum}-screenshot-{dateTime}.png")
            await page.screenshot({'path': f"error_{usernum}-screenshot-{dateTime}.png"})
            logger.info(f"页面HTML保存到： error_{usernum}-html-{dateTime}.html")
            content = await page.content()
            with open(f"error_{usernum}-html-{dateTime}.html", 'w', encoding='utf-8') as f:
                f.write(content)
            await browser.close()
            await deleteSession(workList, uid)
            workList[uid].status = "error"
            workList[uid].msg = "异常退出"
            raise e

    logger.info("任务完成退出")
    logger.info("开始删除缓存文件......")
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
    logger.info("缓存文件已删除！")
    logger.info("开始关闭浏览器....")
    await browser.close()
    logger.info("浏览器已关闭！")
    return

async def typeIDCard(page, workList, uid):
    logger.info("开始输入身份证")

    async def get_verification_IDCard(workList, uid):
        logger.info("开始从全局变量获取身份证")
        retry = 60
        while not workList[uid].ID_CARD and not retry < 0:
            await asyncio.sleep(1)
            retry -= 1
        if retry < 0:
            workList[uid].status = "error"
            workList[uid].msg = "输入身份证超时"
            return

        workList[uid].status = "pending"
        return workList[uid].ID_CARD

    ID_CARD = await get_verification_IDCard(workList, uid)
    if not ID_CARD:
        return

    workList[uid].status = "pending"
    workList[uid].msg = "正在通过身份证验证"
    logger.info("正在输入身份证。。。。。")
    input_elements = await page.JJ('.input-container.id-wrap > div')
    await input_elements[0].click()
    for ID in ID_CARD:
        await page.keyboard.type(str(ID))
        await page.waitFor(random.randint(100, 2000))
    await page.click(".btn.J_ping")
    await page.waitFor(3000)

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
    logger.info("开始输入账号密码")
    await page.waitForSelector(".J_ping.planBLogin")
    await page.click(".J_ping.planBLogin")
    await page.type(
        "#username", usernum, {"delay": random.randint(60, 121)}
    )
    await page.type(
        "#pwd", passwd, {"delay": random.randint(100, 151)}
    )
    await page.waitFor(random.randint(100, 2000))
    await page.click(".policy_tip-checkbox")
    await page.waitFor(random.randint(100, 2000))
    await page.click(".btn.J_ping.active")
    await page.waitFor(random.randint(100, 2000))


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
    logger.info("开始发送验证码")

    try:
        while True:
            if await page.xpath('//*[@id="slot_img"]'):
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
        logger.info("进行发送验证码前置操作")
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
    logger.info("开始发送验证码")

    try:
        while True:
            if await page.xpath('//*[@id="slot_img"]'):
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
    logger.info("开始输入验证码")

    async def get_verification_code(workList, uid):
        logger.info("开始从全局变量获取验证码")
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
    logger.info("开始输入验证码")

    async def get_verification_code(workList, uid):
        logger.info("开始从全局变量获取验证码")
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
                logger.info("清除验证码输入框中已有的验证码")
                await page.evaluate(
                    '(element) => element.value = ""', input_elements[0]
                )

    except Exception as e:
        logger.info("typeSMScode" + str(e))

    await input_elements[0].type(code)
    await page.waitForXPath('//*[@id="app"]/div/div[2]/a[1]')
    await page.waitFor(random.randint(1, 3) * 1000)
    elements = await page.xpath('//*[@id="app"]/div/div[2]/a[1]')
    await elements[0].click()
    await page.waitFor(random.randint(2, 3) * 1000)


async def verification(page):
    logger.info("开始过滑块验证")
    
    try:
        # 1. 获取滑块和背景图
        await page.waitForSelector("#main_img", timeout=5000)
        logger.info("已定位滑块背景图元素")
        
        image_src = await page.Jeval("#main_img", 'el => el.getAttribute("src")')
        logger.info(f"背景图SRC: {image_src[:30]}...")
        
        request.urlretrieve(image_src, "image.png")
        logger.info("背景图下载完成")

        # 2. 获取模板图
        template_src = await page.Jeval("#slot_img", 'el => el.getAttribute("src")')
        logger.info(f"滑块模板SRC: {template_src[:30]}...")
        
        request.urlretrieve(template_src, "template.png")
        logger.info("滑块模板下载完成")

        # 3. 获取实际显示尺寸
        bg_width = await page.evaluate('() => document.getElementById("main_img").clientWidth')
        bg_height = await page.evaluate('() => document.getElementById("main_img").clientHeight')
        logger.info(f"背景图显示尺寸: {bg_width}x{bg_height}")
        
        slot_width = await page.evaluate('() => document.getElementById("slot_img").clientWidth')
        slot_height = await page.evaluate('() => document.getElementById("slot_img").clientHeight')
        logger.info(f"滑块显示尺寸: {slot_width}x{slot_height}")

        # 4. 调整图片到显示尺寸
        for path, size in [("image.png", (bg_width, bg_height)), 
                          ("template.png", (slot_width, slot_height))]:
            img = Image.open(path)
            img = img.resize(size)
            img.save(path)
        logger.info("图片尺寸调整完成")

        # 5. 计算滑块距离
        logger.info("开始计算滑动距离...")
        
        img = cv2.imread("image.png", 0)
        template = cv2.imread("template.png", 0)
        
        # 增强边缘检测
        img = cv2.GaussianBlur(img, (5, 5), 0)
        template = cv2.GaussianBlur(template, (5, 5), 0)
        
        bg_edge = cv2.Canny(img, 50, 150)
        cut_edge = cv2.Canny(template, 50, 150)
        
        # 可视化边缘检测结果（调试用）
        cv2.imwrite("debug_bg_edge.png", bg_edge)
        cv2.imwrite("debug_slot_edge.png", cut_edge)
        logger.info("边缘检测结果已保存")
        
        # 模板匹配
        res = cv2.matchTemplate(bg_edge, cut_edge, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        logger.info(f"匹配结果: 最大相似度={max_val:.2f}, 位置={max_loc}")
        
        # 计算滑块中心点到缺口中心的距离
        slot_center_x = max_loc[0] + slot_width // 2
        distance = slot_center_x - 10  # 减去初始偏移
        
        logger.info(f"计算滑动距离: {distance}px")

        # 6. 执行滑块拖动
        logger.info("开始模拟拖动滑块...")
        
        slider = await page.querySelector(
            "#captcha_modal > div > div.captcha_footer > div > div.sp-msg"
        ) or await page.querySelector(
            "#captcha_modal > div > div.captcha_footer > div > img"
        )
        
        if not slider:
            logger.error("未找到滑块元素!")
            return
            
        box = await slider.boundingBox()
        start_x = box["x"] + 10
        start_y = box["y"] + 10
        
        # 移动到滑块位置
        await page.mouse.move(start_x, start_y)
        await page.mouse.down()
        await asyncio.sleep(0.2)
        
        # 分段拖动模拟人类操作
        steps = 6
        drag_log = []
        current_x = start_x
        
        for i in range(steps):
            # 变速拖动：先快后慢
            if i < steps * 0.7:
                step_size = distance * 0.8 / (steps * 0.7)
            else:
                step_size = distance * 0.2 / (steps * 0.3)
                
            # 添加随机抖动
            current_x += step_size + random.uniform(-1, 1)
            
            # 记录拖动轨迹（调试用）
            drag_log.append((current_x, start_y))
            
            await page.mouse.move(current_x, start_y)
            await asyncio.sleep(random.uniform(0.03, 0.08))
        
        # 最终微调
        for _ in range(3):
            current_x += random.uniform(-1, 1)
            await page.mouse.move(current_x, start_y)
            await asyncio.sleep(0.1)
        
        # 释放鼠标
        await page.mouse.up()
        logger.info(f"滑块拖动完成，轨迹点: {len(drag_log)}个")
        
        # 保存轨迹图像（调试用）
        debug_img = cv2.imread("image.png")
        for x, y in drag_log:
            cv2.circle(debug_img, (int(x - start_x), 50), 2, (0, 0, 255), -1)
        cv2.imwrite("debug_drag_path.png", debug_img)
        logger.info("拖动轨迹已保存至 debug_drag_path.png")
        
    except Exception as e:
        logger.error(f"滑块验证失败: {str(e)}")
        logger.exception(e)
        
        # 保存错误截图
        await page.screenshot({'path': 'slider_error.png'})
        logger.error("错误截图已保存至 slider_error.png")
        raise


async def verification_shape(page):
    logger.info("开始过颜色、形状验证")

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
    i = 5
    while i > 0:
        i -= 1
        await page.waitForSelector("div.captcha_footer img")
        image_src = await page.Jeval(
            "#main_img", 'el => el.getAttribute("src")'
        )
        request.urlretrieve(image_src, "shape_image.png")
        width = await page.evaluate(
            '() => { return document.getElementById("main_img").clientWidth; }'
        )
        height = await page.evaluate(
            '() => { return document.getElementById("main_img").clientHeight; }'
        )
        image = Image.open("shape_image.png")
        resized_image = image.resize((width, height))
        resized_image.save("shape_image.png")

        b_image = await page.querySelector("#main_img")
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

        button = await page.querySelector("div.captcha_footer button#submit-btn")
        if button is None:
            button = await page.querySelector("button#submit-btn")
        if button is None:
            logger.info("未找到提交按钮")
            raise "未找到提交按钮"
        refresh_button = await page.querySelector("div.captcha_header img.jcap_refresh")
        if refresh_button is None:
            refresh_button = await page.querySelector("div.captcha_header span.jcap_refresh")
        if refresh_button is None:
            refresh_button = await page.querySelector(".jcap_refresh")


        if word.find("色") > 0:
            target_color = word.split("请选出图中")[1].split("的图形")[0]
            if target_color in supported_colors:
                logger.info(f"正在找{target_color}")
                center_x, center_y = get_shape_location_by_color(
                    "shape_image.png", target_color
                )
                if center_x is None and center_y is None:
                    logger.info("识别失败，刷新")
                    if refresh_button is None:
                        logger.info("未找到刷新按钮")
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
                logger.info(f"不支持{target_color}，重试")
                if refresh_button is None:
                    logger.info("未找到刷新按钮")
                    raise "未找到刷新按钮"
                await refresh_button.click()
                await asyncio.sleep(random.uniform(2, 4))
                break
        elif word.find("依次") > 0:
            if retry_count < 1:
                logger.info("文字点选重试失败")
                return "notSupport"
            i = 3
            logger.info("进入文字点选")
            logger.info(f"文字点选第{11 - retry_count}次尝试")
            retry_count -= 1
            target_word = word.replace("\"", "")[-4:]
            logger.info(f"点选字为： {target_word}")
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
            logger.info(f"result: {result}")
            img_xy = {}
            for key, xy in result.items():
                img_xy[key] = (int((xy[0] + xy[2]) / 2), int((xy[1] + xy[3]) / 2))
            not_found = False
            click_points = {}
            for wd in target_word:
                if wd not in img_xy:
                    logger.info(f"\"{wd}\"未找到，识别失败,刷新")
                    if refresh_button is None:
                        logger.info("未找到刷新按钮")
                        raise "未找到刷新按钮"
                    await refresh_button.click()
                    await asyncio.sleep(random.uniform(2, 4))
                    not_found = True
                    break
                center_x, center_y = img_xy[wd]
                click_x, click_y = image_top_left_x + center_x, image_top_left_y + center_y
                click_points[wd] = [click_x, click_y]
            logger.info(click_points)
            if os.path.exists("gray.png"):
                os.remove("gray.png")
            if not_found:
                continue
            logger.info("文字点选识别正常")
            for wd, point in click_points.items():
                logger.info(f"点击\"{wd}\",坐标{point[0]}:{point[1]}")
                await page.mouse.click(point[0], point[1])
                await asyncio.sleep(random.uniform(0.5, 2))
            await button.click()
            await asyncio.sleep(random.uniform(0.3, 1))
            break
        else:
            shape_type = word.split("请选出图中的")[1]
            if shape_type in supported_types:
                logger.info(f"正在找{shape_type}")
                if shape_type == "圆环":
                    shape_type = shape_type.replace("圆环", "圆形")
                center_x, center_y = get_shape_location_by_type(
                    "shape_image.png", shape_type
                )
                if center_x is None and center_y is None:
                    logger.info(f"识别失败,刷新")
                    if refresh_button is None:
                        logger.info("未找到刷新按钮")
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
                logger.info(f"不支持{shape_type},刷新中......")
                if refresh_button is None:
                    logger.info("未找到刷新按钮")
                    raise "未找到刷新按钮"
                await refresh_button.click()
                await asyncio.sleep(random.uniform(2, 4))
                continue
    logger.info("过图形结束")


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
    logger.info(f"登录成功 {ck}")
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
                    logger.info(f"已下载{progress:.2f}%...")
    logger.info("下载完成，进行解压安装....")


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
                logger.info("貌似第一次使用，未找到chrome，正在下载chrome浏览器....")

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
                logger.info("解压安装完成")
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
                logger.info("貌似第一次使用，未找到chrome，正在下载chrome浏览器....")
                logger.info("文件位于github，请耐心等待，如遇到网络问题可到项目地址手动下载")
                download_url = "https://mirrors.huaweicloud.com/chromium-browser-snapshots/Linux_x64/884014/chrome-linux.zip"
                if 'arm' in platform.machine():
                    download_url = "https://playwright.azureedge.net/builds/chromium/1088/chromium-linux-arm64.zip"
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

    logger.info("初始化浏览器。。。。。")
    chromium_path = await init_chrome()
    headless = 'new'
    if platform.system() == "Windows":
        headless = False
    logger.info("进入选择登录方式流程")

    try_time = 1
    while True:
        if workList[uid].type == "phone":
            logger.info("选择手机号登录")
            result = await loginPhone(chromium_path, workList, uid, headless)
        elif workList[uid].type == "password":
            logger.info("选择密码登录")
            result = await loginPassword(chromium_path, workList, uid, headless)
        if result != "notSupport" or try_time > 5:
            break
        await asyncio.sleep(random.uniform(2, 4))
        logger.info(f"进行第{try_time}次重试")
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
    await deleteSession(workList, uid)
    logger.info("登录完成")
    await asyncio.sleep(10)
