FROM alpine:3.6

LABEL ImageBaseName=saas-manager

ADD . /code

WORKDIR /code

RUN apk add --update --no-cache curl python3 python3-dev build-base linux-headers pcre-dev
RUN pip3 install --upgrade pip
RUN pip3 install -r requirements.txt
RUN apk del python3-dev build-base linux-headers pcre-dev

EXPOSE 3001
