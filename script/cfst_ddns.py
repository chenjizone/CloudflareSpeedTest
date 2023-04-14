#!/usr/bin/env python
# coding=utf-8
import subprocess
from pydantic import BaseModel
import schedule
import os
import json
import traceback
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.dnspod.v20210323 import dnspod_client, models

RESULT_PATH = "/tmp/cloudflare_result.txt"
BIN = "./CloudflareST.exe"


class SysConfig(BaseModel):
    run_interval_minutes: int = 10


class DnsPodProvider(BaseModel):
    ak: str = ...
    sk: str = ...
    endpoint: str = "dnspod.tencentcloudapi.com"

    class Config:
        env_prefix = "dnspod_"


def get_best_ip(file):
    pass


def update_dnspod_record(best_ip, sys_config):
    config = DnsPodProvider()
    cred = credential.Credential(config.ak, config.sk)
    httpProfile = HttpProfile()
    httpProfile.endpoint = config.endpoint
    clientProfile = ClientProfile()
    clientProfile.httpProfile = httpProfile
    client = dnspod_client.DnspodClient(cred, "", clientProfile)
    req = models.ModifyRecordRequest()
    params = {}
    req.from_json_string(json.dumps(params))
    resp = client.ModifyRecord(req)
    print(resp.to_json_string())


def start_job(sysConfig):
    print("Starting test task...")
    try:
        runCode = subprocess.call([BIN, "-o", RESULT_PATH],
                                  shell=True,
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.STDOUT)
        if runCode != 0:
            print("Execute failed, code: %s" % runCode)
            return
        if not os.path.exists(RESULT_PATH):
            print("No result file")
            return
        if os.path.getsize(RESULT_PATH) == 0:
            print("Result file is empty")
            return
        with open(RESULT_PATH) as f:
            bestIp = get_best_ip(f)
        if not bestIp or len(bestIp) == 0:
            print("No best IP found")
            return
        update_dnspod_record(bestIp, sysConfig)
        print("Best IP found: %s, update dns record success..." % bestIp)
    except BaseException:
        traceback.print_exc()


if __name__ == '__main__':
    # load configuration
    config = SysConfig()
    print("Config is", config.json())
    # start cron job
    schedule.every(config.run_interval_minutes).seconds.do(start_job, config)
    while True:
        schedule.run_pending()
