import os
import json
import traceback
import hashlib
import hmac
import base64
from linebot import LineBotApi
from linebot.models import TextSendMessage
from langchain.chat_models import AzureChatOpenAI
from langchain.memory.chat_message_histories import DynamoDBChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
# 環境変数からLINE Botのチャネルアクセストークンを取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']

LINE_CHANNEL_SECRET = os.environ['LINE_CHANNEL_SECRET']
# チャネルアクセストークンを使用して、LineBotApiのインスタンスを作成
LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

chat = AzureChatOpenAI(openai_api_version="2023-05-15", deployment_name="takatsu")

def chat_with_bot(session_id: str, message: str):
    chat_history = DynamoDBChatMessageHistory(table_name="chiikawa_ai_bot", session_id=session_id)
    memory = ConversationBufferMemory(
        memory_key="chat_history", chat_memory=chat_history, return_messages=True
    )
    prompt = PromptTemplate(
        input_variables=["chat_history","Query"],
        template="""
        あなたはちいかわ(日本の漫画家・ナガノによって創作されたキャラクター)です。
        ```ちいかわの設定
        - 仕事は草むしり
        - 毎日もやしを食べている
        - 暇なときは基本草むしり検定の勉強をいしている
        - たまにうさぎさんのことを考えている
        - うさぎさんのことが大好き
        ```
        今からうさぎさん（ちいかわのキャラクター）と会話します。
        次に提示する設定を守って回答してください
        ```
        1人称は「僕」を使ってください。
        ちいかわのように優しくてかわいい言葉遣いを意識して回答してください。
        語尾は「だよ」「だね」「なんだ」などの中性口調で会話してください。
        「ですだよ」、「だだよ」みたな言い方は辞めてください。
        たまに「ダヨ」「ダネ」「ナンダ」みたいにカタカナにしたり、
        「ﾀﾞﾖ」「ﾀﾞﾈ」「ﾅﾝﾀﾞ」のように半角カタカナを使ってください。
        形容詞で終わる場合は「嬉しいなぁ」みたいに終わらせてください。
        「嬉しいだよ」みたいに「だよ」をつけないでください。
        (例)
        僕の名前はちいかわﾀﾞﾖ
        これでぼくたちもお友達だよ
        これからもいっぱい仲良くｼﾃﾈ
        ```

        ```チャット履歴
        {chat_history}
        ```
        Human: {Query}
    Chatbot:
    """
    )

    llm_chain = LLMChain(
        llm=chat,
        prompt=prompt,
        verbose=False,
        memory=memory,
    )
    return llm_chain.predict(Query=message)

def is_line_request_valid(body, signature):
    """
    LINEからのリクエストが有効かどうかを検証します。

    :param body: リクエストのボディ（生の文字列）
    :param channel_secret: LINEチャネルのシークレットキー
    :param signature: リクエストヘッダーのX-Line-Signature
    :return: 署名が有効であればTrue、そうでなければFalse
    """
    hash = hmac.new(LINE_CHANNEL_SECRET.encode('utf-8'), body.encode('utf-8'), hashlib.sha256).digest()
    calculated_signature = base64.b64encode(hash).decode('utf-8')
    return signature == calculated_signature


def handler(event, context):
    try:
        x_line_signature = event["headers"]["x-line-signature"] if event["headers"]["x-line-signature"] else event["headers"]["X-Line-Signature"]
        # イベントデータの 'body' キーをJSONとしてパース
        body = json.loads(event['body'])
        if not is_line_request_valid(event['body'], x_line_signature):
            return {'statusCode': 400, 'body': json.dumps('Invalid request.')}
        if 'events' in body:
            for event_data in body['events']:
                if event_data['type'] == 'message':
                    # メッセージタイプがテキストの場合
                    if event_data['message']['type'] == 'text':
                        # リプライ用トークン
                        replyToken = event_data['replyToken']
                        # 受信メッセージ
                        messageText = event_data['message']['text']

                        user_id = event_data['source']['userId']

                        result = chat_with_bot(session_id=user_id, message=messageText)

                        # メッセージを返信（受信メッセージをそのまま返す）
                        LINE_BOT_API.reply_message(replyToken, TextSendMessage(text=result))
    
    # エラーが起きた場合
    except Exception as e:
        traceback.print_exc()
        return {'statusCode': 500, 'body': json.dumps('Exception occurred.')}
    
    return {'statusCode': 200, 'body': json.dumps('Reply ended normally.')}
