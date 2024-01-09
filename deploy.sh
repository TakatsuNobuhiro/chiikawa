#!/bin/bash

# DockerイメージをAmazon ECRにプッシュするためのスクリプト
# aws ログイン認証
aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin 176870417049.dkr.ecr.ap-northeast-1.amazonaws.com

# Dockerコンテナをビルド
docker build -t chiikawa .

# Dockerイメージにタグを付ける
docker tag chiikawa:latest 176870417049.dkr.ecr.ap-northeast-1.amazonaws.com/chiikawa:latest

# DockerイメージをAmazon ECRにプッシュ
docker push 176870417049.dkr.ecr.ap-northeast-1.amazonaws.com/chiikawa:latest

# Lambda関数をデプロイ
aws lambda update-function-code --function-name salon-linebot --image-uri 176870417049.dkr.ecr.ap-northeast-1.amazonaws.com/salon:latest

