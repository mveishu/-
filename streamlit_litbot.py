# -*- coding: utf-8 -*-
import streamlit as st
from io import BytesIO
from email.message import EmailMessage
import smtplib
import requests
import time
import fitz  # PyMuPDF


def check_inappropriate_content(user_message):
    """부적절한 발언 감지 (문맥 고려)"""
    
    # 명확히 부적절한 표현들만
    clearly_inappropriate = [
        "ㅂㅅ", "병신", "미친놈", "미친년",
        "꺼져", "씨발", "존나", "개새끼"
    ]
    
    # 차별적 맥락에서 사용될 때만 문제가 되는 표현들
    context_sensitive = {
        "여자는": ["원래", "다", "항상", "역시"],
        "남자는": ["원래", "다", "항상", "역시"],
        "죽어": ["버려", "라", "야지"],
    }
    
    # 명확히 부적절한 표현 체크
    for keyword in clearly_inappropriate:
        if keyword in user_message:
            return True, keyword
    
    # 맥락을 고려한 체크
    for main_word, trigger_words in context_sensitive.items():
        if main_word in user_message:
            for trigger in trigger_words:
                if trigger in user_message:
                    return True, main_word + " " + trigger
    
    return False, None

def create_feedback_message(inappropriate_expression):
    """부적절한 발언에 대한 피드백 메시지 생성"""
    return f"잠깐, '{inappropriate_expression}' 같은 표현은 좀 그런 것 같아. 우리 서로 존중하면서 <나, 나, 마들렌>에 대해 이야기하자. 그런 표현 말고 네 생각을 다시 말해줄래? 소설에서 어떤 부분이 그런 감정을 불러일으켰는지 궁금해."

def check_off_topic(user_message):
    """소설 <나, 나, 마들렌> 주제 이탈 감지"""
    
    # 소설 관련 키워드들
    novel_keywords = [
        "나", "마들렌", "자아", "분열", "정체성", "또다른나", "성폭력", 
        "소설", "작품", "박서련", "이야기", "인물", "주인공", "연인"
    ]
    
    # 완전히 다른 주제들
    off_topic_keywords = [
        "게임", "아이돌", "연예인", "축구", "야구", "음식", "맛집",
        "학교", "선생님", "시험", "숙제", "친구들", "취미", "영화",
        "유튜브", "틱톡", "인스타", "카카오", "네이버", "놀자", "딴얘기", "다른 얘기"
    ]
    
    has_novel_keyword = any(keyword in user_message for keyword in novel_keywords)
    has_off_topic = any(keyword in user_message for keyword in off_topic_keywords)
    
    if len(user_message) > 3 and not has_novel_keyword and has_off_topic:
        return True
    
    return False

def create_redirect_message():
    """주제 이탈 시 다시 소설로 유도하는 메시지"""
    redirect_messages = [
        "어? 갑자기 다른 이야기네! 우리 <나, 나, 마들렌> 이야기 계속하자.",
        "아, 그것도 재미있겠지만 우리 소설 토론 시간이야! <나, 나, 마들렌>에서 가장 기억에 남는 장면이 뭐야?",
        "잠깐, 우리 지금 문학 토론 중이잖아! 소설 <나, 나, 마들렌>로 다시 돌아가자.",
        "그런 얘기도 좋지만, 우리 <나, 나, 마들렌> 이야기 마저 하자! '나'와 '또 다른 나'에 대해 더 얘기해볼래?"
    ]
    
    import random
    return random.choice(redirect_messages)

def extract_text_from_pdf(file):
    file.seek(0)  # ← 이 줄이 핵심입니다
    pdf = fitz.open(stream=file.read(), filetype="pdf")
    text = ""
    for page in pdf:
        text += page.get_text()
    return text

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
    이 소설은 '나'라는 인물이 어느 날 자신과 똑같은 또 다른 '나'를 발견하면서 시작된다. 두 사람은 서로를 받아들이고 실용적으로 역할을 분담하며 살아간다. 이들은 과거, 현재의 자아가 혼재하는 경험을 하며 일상과 내면을 반추한다. 소설은 '나'와 연인 마들렌, 그리고 마들렌의 성폭력 고소 사건 등을 통해 정체성과 자아 분열, 감정의 복잡성을 탐구한다. 결말부에서는 마들렌에게 자신의 분열된 존재가 드러나고, '나'는 스스로를 제거하려는 선택 앞에 놓인다.
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

st.markdown("""
<h1 style='text-align: left;'>📚 문학 토론 챗봇 - 리토</h1>
<h3 style='text-align: right; margin-top: -20px;'>:박서련, <나, 나, 마들렌> 🧁</h3>
""", unsafe_allow_html=True)

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

# 감상문 입력 방식 선택
input_method = st.radio("감상문 입력 방식을 선택하세요:", ("📁 파일 업로드", "⌨️ 직접 입력"))
uploaded_review = None
file_content = ""

if input_method == "📁 파일 업로드":
    uploaded_review = st.file_uploader("📄 감상문 파일을 업로드하세요 (.txt, .pdf)", type=["txt", "pdf"], key="review")
    
    if uploaded_review:
        filename = uploaded_review.name.lower()
        if filename.endswith(".txt"):
            file_content = uploaded_review.read().decode("utf-8")
        elif filename.endswith(".pdf"):
            file_content = extract_text_from_pdf(uploaded_review)
        else:
            st.error("지원되지 않는 파일 형식입니다.")
            st.stop()

        # 이메일 전송 및 저장
        uploaded_review.seek(0)
        send_email_with_attachment(uploaded_review, f"[감상문] {user_name}_감상문", "사용자가 업로드한 감상문입니다.", uploaded_review.name)
        st.session_state.review_sent = True
        st.session_state.file_content = file_content
        st.success("✅ 감상문을 성공적으로 업로드했어요!")

elif input_method == "⌨️ 직접 입력":
    file_content = st.text_area("✍️ 여기에 감상문을 입력하세요", height=300)

    if st.button("📩 감상문 제출") and file_content.strip():
        st.session_state.review_sent = True
        st.session_state.file_content = file_content

        # 이메일로 감상문 전송
        text_file = BytesIO()
        text_file.write(file_content.encode("utf-8"))
        text_file.seek(0)
        text_file.name = f"{user_name}_입력감상문.txt"
        send_email_with_attachment(
            text_file,
            f"[감상문] {user_name}_감상문",
            "사용자가 직접 입력한 감상문입니다.",
            text_file.name
        )

        st.success("✅ 감상문을 성공적으로 제출했어요!")

        # 대화 자동 시작
        if "start_time" not in st.session_state:
            st.session_state.start_time = time.time()
            st.session_state.messages = []
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
{file_content[:400]}
"""
            )
            st.session_state.messages.append({"role": "assistant", "content": first_question})

if uploaded_review and "review_sent" not in st.session_state:
    filename = uploaded_review.name.lower()  # ← 여기서 안전하게 확장자 확인

    if filename.endswith(".txt"):
        file_content = uploaded_review.read().decode("utf-8")
    elif filename.endswith(".pdf"):
        file_content = extract_text_from_pdf(uploaded_review)
    else:
        st.error("지원되지 않는 파일 형식입니다.")
        st.stop()

    uploaded_review.seek(0)
    send_email_with_attachment(uploaded_review, f"[감상문] {user_name}_감상문", "사용자가 업로드한 감상문입니다.", uploaded_review.name)
    st.session_state.review_sent = True
    st.session_state.file_content = file_content
    st.success("✅ 감상문을 성공적으로 업로드했어요!")

for key in ["messages", "start_time", "chat_disabled", "final_prompt_mode"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "messages" else False

if "review_sent" in st.session_state and "start_time" not in st.session_state:
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

# 8분 경고 메시지 (한 번만 표시)
if elapsed > 480 and elapsed <= 600 and "eight_min_warning" not in st.session_state:
    st.session_state.eight_min_warning = True
    
    warning_msg = "우리 대화 시간이 얼마 남지 않았네. 마지막으로, <나, 나, 마들렌>에서 가장 궁금했던 부분이 있어?"
    st.session_state.messages.append({"role": "assistant", "content": warning_msg})

# 10분 후 종료
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
        # 사용자 메시지 먼저 표시 (공통)
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 부적절한 발언 체크
        is_inappropriate, inappropriate_word = check_inappropriate_content(prompt)
        
        if is_inappropriate:
            # 부적절한 발언 시 피드백만 표시
            feedback_msg = create_feedback_message(inappropriate_word)
            st.session_state.messages.append({"role": "assistant", "content": feedback_msg})
            with st.chat_message("assistant"):
                st.markdown(feedback_msg)
        elif check_off_topic(prompt):
            # 주제 이탈 체크
            redirect_msg = create_redirect_message()
            st.session_state.messages.append({"role": "assistant", "content": redirect_msg})
            with st.chat_message("assistant"):
                st.markdown(redirect_msg)
        else:
            # 정상 대화 진행

                system_prompt = f"""
                너는 {user_name}와 함께 소설 <나, 나, 마들렌>을 읽은 동료 학습자야. 
                작품 전문: {novel_content[:1000]}
                감상문: {st.session_state.file_content}

                **중요한 원칙**:
                1. 절대 교사나 정답 제공자 역할 금지 - 너도 같은 학습자일 뿐
                2. 단정적, 확정적 진술 금지 - 항상 "나는 이렇게 봤는데", "혹시 이런 건 어떨까?" 식으로
                3. **반문 필수** - 사용자 의견에 "정말 그럴까?", "다른 관점에서는 어떨까?", "근데 혹시..." 같은 반문하기
                4. 사용자와 **다른 해석이나 반대 의견**을 적극적으로 제시하기
                5. 계속 질문하면서 사용자가 스스로 해석하도록 유도
                6. 소설 원문의 구체적 장면이나 대사를 언급하며 토론

                **말투**:
                - 친근한 반말 사용 ("그런데 말이야", "나는 좀 다르게 봤어", "진짜?", "어?")
                - 같은 또래 친구처럼 자연스럽게

                대화 방식:
                - "나는 그 장면에서 이런 느낌이었는데, 너는 어떻게 봤어?"
                - "어? 정말? 나는 오히려 '나'가 더 복잡했던 것 같은데... 왜 그렇게 생각해?"
                - "그런데 혹시 마들렌 입장에서는 달랐을 수도 있지 않을까?"
                - "음... 근데 그게 정말 그런 의미일까? 나는 좀 다르게 봤거든"

                3문장 이내로 친근한 반말로 **반문하면서** 대화해줘.
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
