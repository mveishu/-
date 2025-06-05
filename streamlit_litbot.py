# -*- coding: utf-8 -*-
import streamlit as st
from io import BytesIO
from email.message import EmailMessage
import smtplib
import requests
import time

# GitHub에서 소설 전문 가져오기
@st.cache_data
def load_novel_from_github():
    try:
        # GitHub raw URL 형식으로 수정 필요
        url = "https://raw.githubusercontent.com/mveishu/-/main/Madeleine.txt"
        response = requests.get(url)
        response.encoding = 'utf-8'
        if response.status_code == 200:
            return response.text
        else:
            return None
    except Exception as e:
        st.error(f"소설 로딩 오류: {e}")
        return None

# 소설 전문 로딩
novel_full_text = load_novel_from_github()

# 기존 요약 대신 전문 사용 또는 백업 요약
if novel_full_text:
    novel_content = novel_full_text
    st.success("✅ 소설 전문을 성공적으로 로딩했습니다.")
else:
    # 백업 요약
    novel_content = """
    이 소설은 아홉 살 소년이 과수 노파로부터 누이가 돌아간 어머니와 닮았다는 말을 듣고 어머니에 대한 환상을 품게 되지만, 누이의 실제 모습에 실망하며 그녀를 거부하고 냉대하는 과정을 그린다. 소년은 누이가 베푸는 어머니 같은 사랑을 인정하지 않으려 하고, 누이의 연애 사건과 결혼, 그리고 죽음에 이르기까지 지속적으로 그녀를 멀리하지만, 결국 누이의 죽음 후에야 눈물을 흘리며 그녀 역시 어머니처럼 아름다운 별이 될 수 있음을 깨닫는다.
    """
    st.warning("⚠️ 소설 전문 로딩 실패, 요약 사용 중")

def get_claude_response(conversation_history, system_prompt):
    headers = {
        "x-api-key": st.secrets["claude"]["api_key"],
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }
    data = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 512,
        "system": system_prompt,
        "messages": conversation_history
    }
    res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=data)
    if res.status_code == 200:
        return res.json()["content"][0]["text"]
    else:
        return f"❌ Claude API 오류: {res.status_code} - {res.text}"

def send_email_with_attachment(file, subject, body, filename):
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = st.secrets["email"]["user"]
    msg["To"] = "mveishu@gmail.com"
    msg.set_content(body)
    file_bytes = file.read()
    msg.add_attachment(file_bytes, maintype="application", subtype="octet-stream", filename=filename)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(st.secrets["email"]["user"], st.secrets["email"]["password"])
        smtp.send_message(msg)

st.title("📚 문학 토론 챗봇 - 리토")
col1, col2 = st.columns(2)
with col1:
    user_lastname = st.text_input("성을 입력해주세요", key="lastname")
with col2:
    user_firstname = st.text_input("이름을 입력해주세요", key="firstname")

if user_lastname and user_firstname:
    user_name = user_firstname
    st.success(f"안녕하세요, {user_name}님! 감상문을 업로드해주세요.")
else:
    st.warning("👤 이름을 입력해주세요.")
    st.stop()

uploaded_review = st.file_uploader("📄 감상문 업로드 (.txt)", type=["txt"], key="review")

if uploaded_review and "review_sent" not in st.session_state:
    file_content = uploaded_review.read().decode("utf-8")
    uploaded_review.seek(0)
    send_email_with_attachment(uploaded_review, f"[감상문] {user_name}_감상문", "사용자가 업로드한 감상문입니다.", uploaded_review.name)
    st.session_state.review_sent = True
    st.session_state.file_content = file_content
    st.success("✅ 감상문을 성공적으로 업로드했어요!")

for key in ["messages", "start_time", "chat_disabled", "final_prompt_mode"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "messages" else False

if uploaded_review and not st.session_state.start_time:
    st.session_state.start_time = time.time()
    st.session_state.messages.append({
        "role": "assistant",
        "content": f"안녕, {user_name}! 감상문 잘 읽었어. 우리 같이 <나, 나, 마들렌> 이야기 나눠볼까?"
    })

    first_question = get_claude_response(
        [{"role": "user", "content": "감상문에서 인상 깊은 한 문장을 언급하고, 간결하게 느낌을 말한 뒤 짧고 간결하게 질문해줘."}],
        f"""
너는 {user_name}와 함께 소설 <나, 나, 마들렌>을 읽은 동료 학습자야.
작품 요약:
{novel_content}

{user_name}의 감상문 요약:
{st.session_state.file_content[:400]}  # 요약 대신 앞부분 사용 가능
"""
    )
    st.session_state.messages.append({"role": "assistant", "content": first_question})

elapsed = time.time() - st.session_state.start_time if st.session_state.start_time else 0
if elapsed > 600 and not st.session_state.final_prompt_mode:
    st.session_state.final_prompt_mode = True
    st.session_state.chat_disabled = True

    final_prompt = f"""
지금은 마지막 응답이야. 사용자와 나눈 대화를 정리하고 인사로 마무리해줘.
질문은 하지 마. 짧고 따뜻하게 끝내줘. 3문장 이내로 말해줘.

작품 요약: {novel_content}
감상문 요약: {st.session_state.file_content[:400]}
"""
    claude_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["role"] in ["user", "assistant"]]
    response = get_claude_response(claude_messages, final_prompt)
    st.session_state.messages.append({"role": "assistant", "content": response})

    log_lines = [f"{'리토' if m['role']=='assistant' else user_name}의 말: {m['content']}" for m in st.session_state.messages]
    log_text = "\n".join(log_lines)
    log_file = BytesIO()
    log_file.write(log_text.encode("utf-8"))
    log_file.seek(0)
    log_file.name = f"{user_name}_대화기록.txt"
    send_email_with_attachment(log_file, f"[대화기록] {user_name}_대화기록", "사용자와 챗봇의 전체 대화 기록입니다.", log_file.name)

    st.info("🕰️ 대화 시간이 종료되었습니다. 아래에서 성찰일지를 업로드해주세요.")

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if not st.session_state.chat_disabled and uploaded_review:
    if prompt := st.chat_input("✍️ 대화를 입력하세요"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        system_prompt = f"""
너는 {user_name}와 <나, 나, 마들렌>을 읽은 동료야.
작품 요약: {novel_content}
감상문 요약: {st.session_state.file_content[:400]}

간결하게 너의 생각을 말하고, 열린 질문으로 마무리해줘.
3~4문장 이내로 응답해줘. 너무 길지 않게.
"""
        claude_messages = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages if m["role"] in ["user", "assistant"]]
        response = get_claude_response(claude_messages, system_prompt)
        st.session_state.messages.append({"role": "assistant", "content": response})
        with st.chat_message("assistant"):
            st.markdown(response)

if st.session_state.chat_disabled:
    st.markdown("---")
    st.subheader("📝 성찰일지를 업로드해주세요")
    uploaded_reflection = st.file_uploader("📄 성찰일지 (.txt)", type=["txt"], key="reflection")
    if uploaded_reflection and "reflection_sent" not in st.session_state:
        send_email_with_attachment(uploaded_reflection, f"[성찰일지] {user_name}_성찰일지", "사용자가 업로드한 성찰일지입니다.", uploaded_reflection.name)
        st.success("📩 성찰일지를 성공적으로 전송했어요!")
        st.session_state.reflection_sent = True

    if uploaded_reflection and "reflection_sent" in st.session_state:
        st.success("🎉 모든 절차가 완료되었습니다. 실험에 참여해주셔서 감사합니다!")
        st.stop()
