import json
import random
import sys
import time
from pathlib import Path
from typing import Optional

from loguru import logger
from selenium import webdriver
from selenium.common import NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium_stealth import stealth

import argparse


class Engine:
    def __init__(self, show_browser=False):
        self.login_url = "https://sso.buaa.edu.cn/login?service=https://yjsxk.buaa.edu.cn/yjsxkapp/sys/xsxkappbuaa/*default/index.do"
        self.app_url = "https://yjsxk.buaa.edu.cn/yjsxkapp/sys/xsxkappbuaa/index.html"
        self.course_url = "https://yjsxk.buaa.edu.cn/yjsxkapp/sys/xsxkappbuaa/course.html"
        self.test_url = "https://bot.sannysoft.com/"

        options = webdriver.ChromeOptions()
        if not show_browser:
            options.add_argument("--headless")

        self.driver = webdriver.Chrome(options=options)

        stealth(
            self.driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win64",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )

    def login(self, seconds=300):
        self.driver.get(self.login_url)
        t = 0
        while t < seconds:
            if self.driver.current_url == self.app_url:
                self.download_cookies()
                return
            t += 1
            self.random_sleep()
        logger.error("Login failed")
        raise ValueError("Login failed")

    def download_cookies(self):
        cookies = self.driver.get_cookies()
        datapath = Path("../data")
        datapath.mkdir(exist_ok=True)
        json.dump(cookies, open(datapath / "cookies.json", "w"), indent=2)

    def load_cookies(self):
        cookies = json.load(open("../data/cookies.json"))
        for cookie in cookies:
            self.driver.add_cookie(cookie)

    def test(self):
        self.driver.get(self.test_url)

    @staticmethod
    def random_sleep(min_time=0.5, max_time=1):
        time.sleep(min_time + random.random() * (max_time - min_time))

    def step(self, course_class: str, course_id: str, course_name: str) -> bool:
        self.driver.refresh()

        while True:
            try:
                tabs_div = self.driver.find_element(By.XPATH, '//*[@id="fanxkTabContainer"]/ul')
                break
            except NoSuchElementException:
                self.random_sleep()

        tab_div_list = tabs_div.find_elements(By.TAG_NAME, "li")
        target_tab = None
        for tab_div in tab_div_list:
            title = tab_div.find_element(By.TAG_NAME, "b").text
            if title == course_class:
                target_tab = tab_div
                logger.debug(f"进入课程类别 {course_class}")
                break

        if target_tab is None:
            logger.error(f"找不到课程类别 {course_class}")
            raise ValueError(f"找不到课程类别 {course_class}")

        target_tab.click()

        while True:
            try:
                search_list = self.driver.find_element(By.XPATH, '//*[@id="fankc_searchInput"]')
                break
            except NoSuchElementException:
                self.random_sleep()

        search_list.send_keys(course_id)
        query_but = self.driver.find_element(By.XPATH, '//*[@id="fankc_queryBtn"]')
        query_but.click()
        self.random_sleep()

        page_buts = self.driver.find_elements(By.XPATH, '//a[@role="goPageIndex"]')

        target_class: Optional[WebElement] = None

        for idx, page_but in enumerate(page_buts):
            if idx > 0:
                page_but.click()
                self.random_sleep()
            class_rows = self.driver.find_elements(By.XPATH, '//tbody/tr')
            for row in class_rows:
                current_class_name = row.find_element(By.XPATH, 'td[1]/a').text
                if current_class_name.strip() == course_id + "-" + course_name:
                    target_class = row
                    break

        if target_class is None:
            logger.error(f"找不到课程 {course_name}")
            raise ValueError(f"找不到课程 {course_name}")

        volume = target_class.find_element(By.XPATH, 'td[9]/span').text
        logger.info(f"课程 {course_name} 容量：{volume}")

        if volume != "已满":
            select_but = target_class.find_element(By.XPATH, 'td[10]/a')
            select_but.click()
            self.random_sleep()
            confirm_but = self.driver.find_element(By.XPATH, '//button[@class="zeromodal-btn zeromodal-btn-primary"]')
            confirm_but.click()
            logger.info(f"选课 {course_name} 成功")
            return True
        else:
            return False

    def workflow(self, course_class: str, course_id: str, course_name: str, min_wait, max_wait):
        self.driver.get(self.course_url)
        self.load_cookies()

        while True:
            try:
                result = self.step(course_class, course_id, course_name)
                if result:
                    break
            except Exception as e:
                logger.error(e)
            self.random_sleep(min_wait, max_wait)


if __name__ == '__main__':
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument("--task", "-t", type=str, required=True, choices=["select", "login"])
    argument_parser.add_argument("--course_class", "-c", type=str, required=False, help="课程所属的类别")
    argument_parser.add_argument("--course_id", "-i", type=str, required=False, help="课程代码")
    argument_parser.add_argument("--course_name", "-n", type=str, required=False, help="完整的课程名称")
    argument_parser.add_argument("--min_wait", type=float, default=2, help="最小等待时间")
    argument_parser.add_argument("--max_wait", type=float, default=8, help="最大等待时间")
    args = argument_parser.parse_args()

    logger.remove(0)
    logger.add(sys.stderr, level="INFO")
    logger.add("log.txt", level="INFO")

    if args.task == "login":
        Engine(show_browser=True).login()
    else:
        print(json.dumps(vars(args), indent=2, ensure_ascii=False))
        for val in vars(args).values():
            if val is None:
                logger.error("参数不完整")
                raise ValueError("参数不完整")
        Engine().workflow(args.course_class, args.course_id, args.course_name, args.min_wait, args.max_wait)
