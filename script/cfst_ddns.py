#!/usr/bin/env python
# coding=utf-8
import subprocess
from pydantic import BaseSettings
import schedule
import os
import json
import traceback
from tencentcloud.common import credential
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.common.profile.http_profile import HttpProfile
from tencentcloud.dnspod.v20210323 import dnspod_client, models
import ssl

ssl._create_default_https_context = ssl._create_unverified_context

RESULT_PATH = "./cloudflare_result.txt"
BIN = "./CloudflareST"


class SysConfig(BaseSettings):
    exec_interval_minutes: int = 10
    exec_cmd_timeout_seconds: int = 300
    exec_expected_minimum_speed_mb: float = 15


class DnsPodProvider(BaseSettings):
    ak: str = ...
    sk: str = ...
    endpoint: str = "dnspod.tencentcloudapi.com"
    line: str = "境内"
    domain: str = ...

    class Config:
        env_prefix = "dnspod_"


class DnsPodService(object):

    def __init__(self):
        self.config = DnsPodProvider()
        self.client = self._new_client(self.config)
        self.subDomain, self.mainDomain = self._parse_domain(
            self.config.domain)
        self.line = self.config.line

    def _new_client(self, config):
        cred = credential.Credential(config.ak, config.sk)
        httpProfile = HttpProfile()
        httpProfile.endpoint = config.endpoint
        clientProfile = ClientProfile()
        clientProfile.httpProfile = httpProfile
        client = dnspod_client.DnspodClient(cred, "", clientProfile)
        return client

    def _get_record_id(self):
        req = models.DescribeRecordListRequest()
        params = {
            "Domain": self.mainDomain,
            "Subdomain": self.subDomain,
            "RecordType": "A",
            "RecordLine": self.line
        }
        req.from_json_string(json.dumps(params))
        resp = self.client.DescribeRecordList(req)
        recordId = None
        for record in resp.RecordList:
            recordId = record.RecordId
            print("Exists record is:", resp.to_json_string())
        return recordId

    def _get_record_ip(self):
        req = models.DescribeRecordListRequest()
        params = {
            "Domain": self.mainDomain,
            "Subdomain": self.subDomain,
            "RecordType": "A",
            "RecordLine": self.line
        }
        req.from_json_string(json.dumps(params))
        resp = self.client.DescribeRecordList(req)
        recordIp = None
        for record in resp.RecordList:
            recordIp = record.Value
            print("Current record ip is:", recordIp)
        return recordIp

    def _update_record(self, recordId, newIp):
        req = models.ModifyRecordRequest()
        params = {
            "Domain": self.mainDomain,
            "SubDomain": self.subDomain,
            "RecordType": "A",
            "RecordLine": self.line,
            "Value": newIp,
            "RecordId": recordId
        }
        req.from_json_string(json.dumps(params))
        resp = self.client.ModifyRecord(req)
        print("Modified success, response is:", resp.to_json_string())

    def _create_record(self, ip):
        req = models.CreateRecordRequest()
        params = {
            "Domain": self.mainDomain,
            "SubDomain": self.subDomain,
            "RecordType": "A",
            "RecordLine": self.line,
            "Value": ip
        }
        req.from_json_string(json.dumps(params))
        resp = self.client.CreateRecord(req)
        print("Created success, response is:", resp.to_json_string())

    def _parse_domain(self, domain):
        return str(domain).split(".", 1)

    def update_dns(self, ip):
        existsRecordId = self._get_record_id()
        if existsRecordId:
            self._update_record(existsRecordId, ip)
        else:
            self._create_record(ip)


def get_best_ip(fp, expectedSpeed):
    lineNo = 0
    bestIp = None
    bestSpeed = 0
    for line in fp:
        lineNo += 1
        if lineNo == 1:
            continue
        lineItems = line.strip().split(",")
        ip = lineItems[0]
        speed = lineItems[len(lineItems) - 1]
        if float(speed) > float(expectedSpeed):
            bestIp = ip
            bestSpeed = speed
        break
    return bestIp, bestSpeed


def get_speed_by_ip(fp, currentIp, expectedSpeed):
    lineNo = 0
    currentSpeed = None
    for line in fp:
        lineNo += 1
        if lineNo == 1:
            continue
        lineItems = line.strip().split(",")
        ip = lineItems[0]
        speed = lineItems[len(lineItems) - 1]
        if ip == currentIp and float(speed) > float(expectedSpeed):
            return speed
    return currentSpeed


def start_job(sysConfig: SysConfig):
    print("Starting test task...")
    try:
        dnspodService = DnsPodService()
        currentIp = dnspodService._get_record_ip()
        runRet = subprocess.run([BIN, "-o", RESULT_PATH, "-ip", currentIp],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                timeout=sysConfig.exec_cmd_timeout_seconds)
        if runRet.returncode != 0:
            print("Execute failed, code: %d" % runRet.returncode)
            for line in runRet.stdout.splitlines():
                print(line)
            return
        with open(RESULT_PATH) as f:
            currentSpeed = get_speed_by_ip(
                f, currentIp, sysConfig.exec_expected_minimum_speed_mb)
            if currentSpeed:
                print(
                    "Task complete, current ip: %s, speed:%sMB/s ,no need to continue"
                    % (currentIp, currentSpeed))
                return
        runRet = subprocess.run([BIN, "-o", RESULT_PATH],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                timeout=sysConfig.exec_cmd_timeout_seconds)
        if runRet.returncode != 0:
            print("Execute failed, code: %d" % runRet.returncode)
            for line in runRet.stdout.splitlines():
                print(line)
            return
        if not os.path.exists(RESULT_PATH):
            print("No result file")
            return
        if os.path.getsize(RESULT_PATH) == 0:
            print("Result file is empty")
            return
        with open(RESULT_PATH) as f:
            bestIp, bestSpeed = get_best_ip(
                f, sysConfig.exec_expected_minimum_speed_mb)
        if not bestIp or len(bestIp) == 0:
            print("No best IP found")
            return
        print("Best IP found: %s, speed: %sMB/s" % (bestIp, bestSpeed))
        dnspodService = DnsPodService()
        dnspodService.update_dns(bestIp)
        print("Task execution complete...")
    except BaseException:
        traceback.print_exc()


if __name__ == '__main__':
    # load configuration
    config = SysConfig()
    print("Config is:", config.dict())
    # start cron job
    schedule.every(config.exec_interval_minutes).minutes.do(start_job, config)
    while True:
        schedule.run_pending()
