#!/usr/bin/env python
# coding=utf-8
import subprocess
from pydantic import BaseModel
import schedule


class SysConfig(BaseModel):
    run_internal_minutes = 10


def start_job():
    print("Starting")
    subprocess.call(["echo", "hello world"],
                    shell=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT)


if __name__ == '__main__':
    # load configuration
    config = SysConfig()
    print("config is", config.json())
    # start cron job
    schedule.every(config.run_internal_minutes).seconds.do(start_job)
    while True:
        schedule.run_pending()
