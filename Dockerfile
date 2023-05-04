FROM golang:alpine as builder 
ENV GO111MODULE=on
ENV GOPROXY=https://goproxy.cn
RUN mkdir /build  
ADD . /build/ 
WORKDIR /build  
RUN go build -o CloudflareST .
FROM python:3.9.16-slim-buster
RUN mkdir /app
WORKDIR /app
COPY --from=builder /build/CloudflareST /app
COPY ./resources/requirements.txt ./script/cfst_ddns.py ./ip.txt ./ipv6.txt ./
RUN pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple && chmod +x ./cfst_ddns.py
CMD ["python","-u","./cfst_ddns.py"]