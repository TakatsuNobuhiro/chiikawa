import os
import json
import traceback
import hashlib
import hmac
import base64
from linebot import LineBotApi
from linebot.models import TextSendMessage
from langchain.chat_models import BedrockChat
from langchain.schema import HumanMessage
from langchain.memory.chat_message_histories import DynamoDBChatMessageHistory
from langchain.memory import ConversationBufferMemory
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
# 環境変数からLINE Botのチャネルアクセストークンを取得
LINE_CHANNEL_ACCESS_TOKEN = os.environ['LINE_CHANNEL_ACCESS_TOKEN']

LINE_CHANNEL_SECRET = os.environ['LINE_CHANNEL_SECRET']
# チャネルアクセストークンを使用して、LineBotApiのインスタンスを作成
LINE_BOT_API = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

chat = BedrockChat(
    model_id="anthropic.claude-v2:1",
    model_kwargs={
        "max_tokens_to_sample": 100000
    }
)

def chat_with_bot(session_id: str, message: str):
    chat_history = DynamoDBChatMessageHistory(table_name="salon_ai_bot", session_id=session_id)
    memory = ConversationBufferMemory(
        memory_key="chat_history", chat_memory=chat_history, return_messages=True
    )
    prompt = PromptTemplate(
        input_variables=["chat_history","Query"],
        template="""あなたは人間と会話をするチャットボットです。

    {chat_history}
    Human: {Query}
    Chatbot:"""
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
