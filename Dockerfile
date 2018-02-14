FROM alpine:3.5

LABEL ImageBaseName=saas-manager

ADD . /code

WORKDIR /code

RUN apk add --update --no-cache curl python3 python3-dev build-base linux-headers pcre-dev
RUN curl https://bootstrap.pypa.io/get-pip.py > get-pip.py && python3 get-pip.py
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN apk del python3-dev build-base linux-headers pcre-dev

EXPOSE 3001
