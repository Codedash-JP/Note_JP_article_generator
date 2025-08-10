import json
from typing import List

import streamlit as st
from google import genai
from google.genai import types

# =========================
# ---- UI THEME (2色) ----
# =========================
PRIMARY = "#1f6feb"   # ブルー
ACCENT  = "#0d1117"   # ダーク

st.set_page_config(page_title="Chaptered Writer (Gemini + Streamlit)", page_icon="✍️", layout="wide")

st.markdown(
    f"""
    <style>
    .stApp {{
        background: linear-gradient(180deg, {ACCENT} 0%, #0b0e14 100%);
        color: #e6edf3;
    }}
    .stTextInput input, .stTextArea textarea {{
        background-color: #0b1220 !important;
        color: #e6edf3 !important;
        border: 1px solid #233554 !important;
    }}
    .stButton>button {{
        background-color: {PRIMARY} !important;
        color: white !important;
        border: 0;
        border-radius: 8px;
        padding: 0.6rem 1rem;
    }}
    .pill {{
        display:inline-block; padding:.2rem .6rem; border-radius:999px; 
        background:{PRIMARY}; color:white; font-size:.8rem; margin-right:.4rem;
    }}
    .card {{
        border:1px solid #223; border-radius:12px; padding:1rem; background:#0b1220;
    }}
    .muted {{ color:#9aa6b2; }}
    /* Sliderラベルと値を白字にする */
    .stSlider label, .stSlider div[data-baseweb="slider"] span {
        color: white !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# =========================
# ---- Session State ----
# =========================
if "outline" not in st.session_state:
    st.session_state.outline = ""
if "chapters" not in st.session_state:
    st.session_state.chapters = []
if "generated_texts" not in st.session_state:
    st.session_state.generated_texts = {}
if "model_name" not in st.session_state:
    st.session_state.model_name = "gemini-2.5-flash"

# =========================
# ---- Sidebar Inputs ----
# =========================
with st.sidebar:
    st.markdown("## ⚙️ 設定")
    api_key = st.text_input("Gemini API Key", type="password", help="Google AI Studioで発行したAPIキーを入力")
    model_name = st.selectbox("モデル", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"], index=0)
    st.session_state.model_name = model_name

    st.markdown("---")
    st.markdown("### ✍️ 書き方の指針 (HOW_TO_WRITE)")
    how_to_write = st.text_area(
        "HOW_TO_WRITE",
        value="なるべく柔らかい文章で、人に寄り添うような形にしてください。極端な表現は避けなさい。",
        height=120
    )

# =========================
# ---- Header ----
# =========================
st.markdown("<span class='pill'>Gemini × Streamlit</span>  **章立て → 推敲 → 本文生成**", unsafe_allow_html=True)
st.title("Chaptered Writer")
st.markdown("<div class='muted'>トピックと書き方を指定 → 章タイトルを生成 → 章リストを編集 → 一括で本文生成。</div>", unsafe_allow_html=True)
st.markdown("")

# =========================
# ---- Topic Input ----
# =========================
topic_default = (
    "宮崎駿の映画に隠されたアニメ制作への思いがテーマです。実は「君たちはどう生きるか」"
    "はスタジオ・ジブリにおける制作の葛藤がテーマとなっていることを指摘します。"
)
topic = st.text_area("TOPIC（テーマ）", value=topic_default, height=120)

colA, colB = st.columns([1, 1])

# =========================
# ---- Gemini helpers ----
# =========================
def build_client(key: str):
    if not key:
        st.warning("Gemini API Key を入力してください。")
        return None
    try:
        client = genai.Client(api_key=key)
        return client
    except Exception as e:
        st.error(f"クライアント初期化に失敗しました: {e}")
        return None

grounding_tool = types.Tool(google_search=types.GoogleSearch())
base_config = types.GenerateContentConfig(tools=[grounding_tool])

def gen_response(client: genai.Client, prompt: str):
    return client.models.generate_content(
        model=st.session_state.model_name,
        contents=prompt,
        config=base_config,
    )

def list_gen(client: genai.Client, prompt: str):
    """List[str] で受け取る"""
    return client.models.generate_content(
        model=st.session_state.model_name,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_schema": list[str],
        },
    )

# =========================
# ---- Step 1: 章タイトル生成 ----
# =========================
with colA:
    st.subheader("① 章タイトルの生成")
    st.markdown("<div class='card'>「開始」ボタンで、まずは概要と章タイトル案（起承転結の4本）を生成します。</div>", unsafe_allow_html=True)
    start = st.button("🚀 開始（章タイトルを生成）", use_container_width=True)

with colB:
    st.subheader("② 章リストの編集")
    st.markdown("<div class='card'>生成された章タイトルを編集・並べ替えして確定してください。</div>", unsafe_allow_html=True)

if start:
    client = build_client(api_key)
    if client:
        with st.spinner("概要と章タイトルを生成中..."):
            try:
                outline_resp = gen_response(
                    client,
                    f"""
以下のテーマでブログ文章を書きます。日本語検索を駆使して概要を書け。
## テーマ ##
{topic}
                    """.strip(),
                )
                outline_text = outline_resp.text or ""
                st.session_state.outline = outline_text

                chapters_resp = list_gen(
                    client,
                    f"""
以下のテーマと概要でブログ文章を書きます。起承転結のある章のタイトルを4つ考え、そのタイトルのみをリスト形式（JSON配列）で示せ。
## テーマ ##
{topic}
## 概要 ##
{outline_text}
                    """.strip(),
                )
                proposed = chapters_resp.parsed or []
                # 念のため文字列化
                st.session_state.chapters = [str(c).strip() for c in proposed if str(c).strip()]
                st.success("章タイトル案を生成しました。右側で編集できます。")
            except Exception as e:
                st.error(f"生成に失敗しました: {e}")

# 概要表示
if st.session_state.outline:
    with st.expander("📝 生成された概要（クリックで展開）", expanded=False):
        st.write(st.session_state.outline)

# 章リスト編集 UI
if st.session_state.chapters:
    st.markdown("#### 現在の章タイトル")
    # data_editor で編集可能なテーブルに
    import pandas as pd

    df = pd.DataFrame({"title": st.session_state.chapters})
    edited_df = st.data_editor(
        df,
        use_container_width=True,
        num_rows="dynamic",
        key="chapters_editor",
        column_config={"title": "章タイトル"},
    )
    # 反映
    st.session_state.chapters = [t for t in edited_df["title"].astype(str).tolist() if t.strip()]

    st.markdown("<div class='muted'>※ 行の追加・削除・並べ替えが可能です（ドラッグで順序変更）。</div>", unsafe_allow_html=True)

# =========================
# ---- Step 3: 本文生成 ----
# =========================
st.markdown("---")
st.subheader("③ 本文を一括生成")
col1, col2 = st.columns([1, 2])
with col1:
    paragraphs = st.slider("各章の段落数", min_value=6, max_value=10, value=8, step=1)
with col2:
    approx_chars = st.slider("1パラグラフあたりの目安文字数", min_value=400, max_value=900, value=800, step=50)

generate = st.button("🖨️ 文章生成", use_container_width=True, disabled=not st.session_state.chapters)

if generate:
    client = build_client(api_key)
    if client:
        st.session_state.generated_texts = {}
        progress = st.progress(0)
        total = max(1, len(st.session_state.chapters))

        for i, chapter_title in enumerate(st.session_state.chapters, start=1):
            with st.spinner(f"生成中: {chapter_title}"):
                try:
                    resp = gen_response(
                        client,
                        f"""
以下のテーマでブログ文章を書きます。そのうちの1つの章が「{chapter_title}」です。
この章に相応しい内容を検索も活用しつつ、{paragraphs} パラグラフの文章で示せ。

## テーマ ##
{topic}

## アウトプットのフォーマット ##
テキストのみ。改行以外の余計な装飾はしないこと。
1パラグラフあたりおよそ {approx_chars} 文字で、しっかりと書くこと。

## 書き方の注意点 ##
{how_to_write}
                        """.strip(),
                    )
                    st.session_state.generated_texts[chapter_title] = resp.text or ""
                except Exception as e:
                    st.session_state.generated_texts[chapter_title] = f"[エラー] この章の生成に失敗しました: {e}"

            progress.progress(i / total)

        st.success("本文生成が完了しました。")

# =========================
# ---- Output Display ----
# =========================
if st.session_state.generated_texts:
    st.markdown("## 📚 生成結果")
    # 章ごとに表示
    for title, body in st.session_state.generated_texts.items():
        st.markdown(f"### {title}")
        st.write(body)

    # ダウンロード用に結合
    compiled = []
    compiled.append(f"# テーマ\n{topic}\n")
    compiled.append("## 概要\n" + (st.session_state.outline or "") + "\n")
    for title, body in st.session_state.generated_texts.items():
        compiled.append(f"## {title}\n{body}\n")
    full_text = "\n".join(compiled)

    st.download_button(
        label="⬇️ テキストをダウンロード",
        data=full_text.encode("utf-8"),
        file_name="generated_article.txt",
        mime="text/plain",
        use_container_width=True,
    )

st.markdown("---")
st.caption("Made with Streamlit + Google Gemini")
