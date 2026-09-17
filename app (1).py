import json
import os
import re
from datetime import datetime
from urllib.parse import urlparse

import requests
import streamlit as st
from bs4 import BeautifulSoup
from fpdf import FPDF

st.set_page_config(page_title="فاحص المتاجر", page_icon="🔍", layout="wide")

LUXURY_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700;800&display=swap');

html, body, [class*="css"] {
    font-family: 'Cairo', sans-serif;
    direction: rtl;
}

.stApp {
    background: radial-gradient(circle at top right, #1a1f2e 0%, #0d1117 55%, #0a0c10 100%);
}

/* Hero header */
.hero {
    background: linear-gradient(135deg, #1c2333 0%, #10131c 100%);
    border: 1px solid rgba(212, 175, 55, 0.25);
    border-radius: 18px;
    padding: 2.2rem 2rem;
    margin-bottom: 1.8rem;
    text-align: center;
    box-shadow: 0 10px 30px rgba(0,0,0,0.35);
}
.hero h1 {
    font-weight: 800;
    font-size: 2.1rem;
    background: linear-gradient(90deg, #d4af37, #f5e7a8, #d4af37);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.4rem;
}
.hero p { color: #9aa4b2; font-size: 1rem; margin: 0; }

/* Metric cards */
.metric-row { display: flex; gap: 1rem; margin: 1.2rem 0; }
.metric-card {
    flex: 1;
    background: linear-gradient(160deg, #171c28, #11141c);
    border: 1px solid rgba(212,175,55,0.18);
    border-radius: 14px;
    padding: 1.1rem 1rem;
    text-align: center;
    box-shadow: 0 6px 18px rgba(0,0,0,0.25);
}
.metric-card .label { color: #9aa4b2; font-size: 0.85rem; margin-bottom: 0.3rem; }
.metric-card .value { color: #f5e7a8; font-size: 1.9rem; font-weight: 800; }

/* Section cards */
.section-card {
    background: rgba(23, 28, 40, 0.65);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 14px;
    padding: 1.3rem 1.4rem;
    margin-bottom: 1rem;
}
.section-card h3 {
    color: #d4af37;
    font-weight: 700;
    margin-top: 0;
    border-bottom: 1px solid rgba(212,175,55,0.2);
    padding-bottom: 0.5rem;
    margin-bottom: 0.8rem;
}

/* Buttons */
.stButton > button, .stDownloadButton > button, .stLinkButton > a {
    border-radius: 10px !important;
    font-weight: 700 !important;
    border: 1px solid rgba(212,175,55,0.4) !important;
}
.stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    background: linear-gradient(135deg, #d4af37, #b8912c) !important;
    color: #10131c !important;
}

/* Badge pills */
.pill { display:inline-block; padding: 0.15rem 0.65rem; border-radius: 999px; font-size: 0.8rem; font-weight:700; margin-inline-end: 0.4rem;}
.pill-ok { background: rgba(46, 204, 113, 0.15); color: #2ecc71; border: 1px solid rgba(46,204,113,0.35); }
.pill-bad { background: rgba(231, 76, 60, 0.15); color: #e74c3c; border: 1px solid rgba(231,76,60,0.35); }

div[data-testid="stExpander"] {
    background: rgba(23, 28, 40, 0.5);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 12px;
}
</style>
"""
st.markdown(LUXURY_CSS, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f"""
    <div class="hero">
        <h1>{title}</h1>
        <p>{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


def metric_row(items):
    cards = "".join(
        f'<div class="metric-card"><div class="label">{label}</div>'
        f'<div class="value">{value}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="metric-row">{cards}</div>', unsafe_allow_html=True)


def pill(ok, text):
    cls = "pill-ok" if ok else "pill-bad"
    icon = "✔" if ok else "✘"
    return f'<span class="pill {cls}">{icon} {text}</span>'


FONT_PATH = os.path.join(os.path.dirname(__file__), "NotoNaskhArabic-Regular.ttf")


def ar(text):
    """يرجّع النص كما هو (بدون تشكيل عربي) عشان يُطبع في الـ PDF."""
    if text is None:
        return ""
    return str(text)


class ReportPDF(FPDF):
    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Arabic", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, ar(f"صفحة {self.page_no()}"), align="C")


def new_pdf():
    pdf = ReportPDF()
    pdf.add_font("Arabic", "", FONT_PATH)
    pdf.set_font("Arabic", "", 12)
    pdf.add_page()
    return pdf


def pdf_title(pdf, text, size=18):
    pdf.set_font("Arabic", "", size)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 12, ar(text), align="R", new_x="LMARGIN", new_y="NEXT")


def pdf_subtitle(pdf, text):
    pdf.ln(2)
    pdf.set_font("Arabic", "", 14)
    pdf.set_text_color(30, 90, 160)
    pdf.cell(0, 10, ar(text), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(20, 20, 20)


def pdf_line(pdf, label, ok=None, value=None):
    pdf.set_font("Arabic", "", 11)
    prefix = ""
    if ok is True:
        prefix = "✔ "
        pdf.set_text_color(30, 140, 60)
    elif ok is False:
        prefix = "✘ "
        pdf.set_text_color(190, 40, 40)
    else:
        pdf.set_text_color(20, 20, 20)
    text = f"{prefix}{label}" + (f": {value}" if value not in (None, "") else "")
    pdf.multi_cell(0, 8, ar(text), align="R")
    pdf.set_text_color(20, 20, 20)



HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

PRICE_PATTERN = re.compile(
    r"(?:ر\.?س|SAR|EGP|USD|\$|ريال)\s?[\d,]+(?:\.\d+)?|[\d,]+(?:\.\d+)?\s?(?:ر\.?س|SAR|EGP|USD|\$|ريال)",
    re.IGNORECASE,
)


def fetch_html(url, timeout=15):
    resp = requests.get(url, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.text, resp.elapsed.total_seconds(), len(resp.content)


def check_seo(soup, base_url):
    result = {}
    title = soup.find("title")
    result["title"] = title.text.strip() if title else None
    result["title_length"] = len(result["title"]) if result["title"] else 0
    result["title_ok"] = 10 <= result["title_length"] <= 65

    meta_desc = soup.find("meta", attrs={"name": "description"})
    result["meta_description"] = meta_desc["content"].strip() if meta_desc and meta_desc.get("content") else None
    result["meta_description_ok"] = bool(result["meta_description"]) and 50 <= len(result["meta_description"] or "") <= 160

    h1_tags = soup.find_all("h1")
    result["h1_count"] = len(h1_tags)
    result["h1_ok"] = len(h1_tags) == 1

    og_tags = soup.find_all("meta", attrs={"property": re.compile(r"^og:")})
    result["has_open_graph"] = len(og_tags) > 0

    json_ld = soup.find_all("script", attrs={"type": "application/ld+json"})
    result["has_structured_data"] = len(json_ld) > 0

    imgs = soup.find_all("img")
    imgs_no_alt = [i for i in imgs if not i.get("alt", "").strip()]
    result["total_images"] = len(imgs)
    result["images_missing_alt"] = len(imgs_no_alt)

    viewport = soup.find("meta", attrs={"name": "viewport"})
    result["has_mobile_viewport"] = bool(viewport)

    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    for path, key in [("/sitemap.xml", "sitemap_found"), ("/robots.txt", "robots_txt_found")]:
        try:
            r = requests.get(root + path, headers=HEADERS, timeout=8)
            result[key] = r.status_code == 200
        except requests.RequestException:
            result[key] = False
    return result


def check_ux(soup, html, url):
    result = {}
    result["has_search_box"] = bool(soup.find("input", attrs={"type": "search"}) or
                                     soup.find(attrs={"placeholder": re.compile("search|بحث", re.I)}))
    result["has_cart_icon"] = bool(re.search(r"cart|سلة|basket", html, re.I))
    result["has_whatsapp_or_chat"] = bool(re.search(r"whatsapp|wa\.me|livechat|zendesk|crisp|tawk", html, re.I))
    result["uses_https"] = url.startswith("https://")
    return result


def check_products(soup, html):
    result = {}
    prices_found = PRICE_PATTERN.findall(html)
    result["sample_prices"] = list(dict.fromkeys(prices_found))[:8]
    product_like = soup.select("[class*=product], [class*=Product], [id*=product], [class*=item-card]")
    result["approx_product_elements_detected"] = len(product_like)
    result["has_add_to_cart_button"] = bool(re.search(r"add\s?to\s?cart|أضف\s?إلى\s?السلة|اضافة للسلة", html, re.I))
    return result


def check_pagespeed(url, api_key):
    if not api_key:
        return {"skipped": True}
    endpoint = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {"url": url, "key": api_key, "strategy": "mobile", "category": "performance"}
    try:
        r = requests.get(endpoint, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        score = data["lighthouseResult"]["categories"]["performance"]["score"]
        metrics = data["lighthouseResult"]["audits"]
        return {
            "performance_score": round(score * 100),
            "largest_contentful_paint": metrics.get("largest-contentful-paint", {}).get("displayValue"),
        }
    except Exception as e:
        return {"error": str(e)}


def score_report(seo, ux, pagespeed):
    seo_score = sum([
        20 if seo.get("title_ok") else 0, 20 if seo.get("meta_description_ok") else 0,
        15 if seo.get("h1_ok") else 0, 15 if seo.get("has_structured_data") else 0,
        15 if seo.get("has_open_graph") else 0, 15 if seo.get("sitemap_found") else 0,
    ])
    ux_score = sum([
        30 if ux.get("has_search_box") else 0, 25 if ux.get("has_cart_icon") else 0,
        25 if ux.get("has_whatsapp_or_chat") else 0, 20 if ux.get("uses_https") else 0,
    ])
    return {"seo_score": seo_score, "ux_score": ux_score, "speed_score": pagespeed.get("performance_score")}


def badge(ok):
    return "✅" if ok else "❌"


def build_audit_pdf(full_report):
    seo, ux, products = full_report["seo"], full_report["ux"], full_report["products"]
    scores = full_report["scores"]

    pdf = new_pdf()
    pdf_title(pdf, "تقرير فحص المتجر", 20)
    pdf.set_font("Arabic", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 7, ar(full_report["url"]), align="R")
    pdf.multi_cell(0, 7, ar("تاريخ الفحص: " + full_report["scanned_at"]), align="R")
    pdf.ln(4)

    pdf_subtitle(pdf, f"الدرجات العامة — SEO: {scores['seo_score']}/100   "
                       f"UX: {scores['ux_score']}/100   "
                       f"السرعة: {scores['speed_score'] if scores['speed_score'] is not None else '—'}")

    pdf_subtitle(pdf, "SEO")
    pdf_line(pdf, "العنوان", seo["title_ok"], seo["title"] or "غير موجود")
    pdf_line(pdf, "الوصف الميتا", seo["meta_description_ok"])
    pdf_line(pdf, f"H1 (عدد {seo['h1_count']})", seo["h1_ok"])
    pdf_line(pdf, "Structured Data", seo["has_structured_data"])
    pdf_line(pdf, "Open Graph", seo["has_open_graph"])
    pdf_line(pdf, "Sitemap", seo["sitemap_found"])
    pdf_line(pdf, f"صور بدون alt text: {seo['images_missing_alt']}/{seo['total_images']}")

    pdf_subtitle(pdf, "تجربة المستخدم")
    pdf_line(pdf, "HTTPS", ux["uses_https"])
    pdf_line(pdf, "خانة بحث", ux["has_search_box"])
    pdf_line(pdf, "سلة واضحة", ux["has_cart_icon"])
    pdf_line(pdf, "واتساب / شات", ux["has_whatsapp_or_chat"])

    pdf_subtitle(pdf, "المنتجات")
    pdf_line(pdf, f"عناصر منتجات مكتشفة: {products['approx_product_elements_detected']}")
    pdf_line(pdf, "زر إضافة للسلة", products["has_add_to_cart_button"])
    if products["sample_prices"]:
        pdf_line(pdf, "أمثلة أسعار: " + "، ".join(products["sample_prices"]))

    pdf_subtitle(pdf, "الأداء العام")
    pdf_line(pdf, f"زمن الاستجابة: {full_report['response_time_seconds']} ثانية")
    pdf_line(pdf, f"حجم الصفحة: {full_report['page_size_kb']} KB")

    return bytes(pdf.output())


# ==================== تبويب 1: فحص المتجر ====================
def render_audit_tab():
    hero("🔍 فاحص المتاجر الإلكترونية", "حط رابط أي متجر واحصل على تقرير SEO وتجربة استخدام ومنتجات في ثواني")

    with st.form("audit_form"):
        url = st.text_input("رابط المتجر", placeholder="https://example-store.com")
        api_key = st.text_input("مفتاح PageSpeed API (اختياري - لدرجة السرعة)", type="password")
        submitted = st.form_submit_button("✨ افحص المتجر", use_container_width=True, type="primary")

    if submitted:
        if not url.startswith("http"):
            st.error("اكتب رابط صحيح يبدأ بـ https://")
        else:
            with st.spinner("جاري فحص المتجر..."):
                try:
                    html, response_time, page_size = fetch_html(url)
                    soup = BeautifulSoup(html, "html.parser")
                    seo = check_seo(soup, url)
                    ux = check_ux(soup, html, url)
                    products = check_products(soup, html)
                    pagespeed = check_pagespeed(url, api_key)
                    scores = score_report(seo, ux, pagespeed)
                except requests.RequestException as e:
                    st.error(f"تعذر الوصول للرابط: {e}")
                    st.stop()

            st.success("تم الفحص ✅")

            metric_row([
                ("SEO", f"{scores['seo_score']}/100"),
                ("تجربة المستخدم", f"{scores['ux_score']}/100"),
                ("السرعة", f"{scores['speed_score']}/100" if scores['speed_score'] is not None else "—"),
            ])

            st.markdown(f"""
            <div class="section-card">
                <h3>🔍 SEO</h3>
                {pill(seo['title_ok'], 'العنوان: ' + (seo['title'] or 'غير موجود'))}
                {pill(seo['meta_description_ok'], 'الوصف الميتا')}
                {pill(seo['h1_ok'], f"H1 (عدد {seo['h1_count']})")}
                {pill(seo['has_structured_data'], 'Structured Data')}
                {pill(seo['has_open_graph'], 'Open Graph')}
                {pill(seo['sitemap_found'], 'Sitemap')}
                <p style="color:#9aa4b2; margin-top:0.8rem;">🖼️ صور بدون alt text: {seo['images_missing_alt']}/{seo['total_images']}</p>
            </div>

            <div class="section-card">
                <h3>🎨 تجربة المستخدم</h3>
                {pill(ux['uses_https'], 'HTTPS')}
                {pill(ux['has_search_box'], 'خانة بحث')}
                {pill(ux['has_cart_icon'], 'سلة واضحة')}
                {pill(ux['has_whatsapp_or_chat'], 'واتساب / شات')}
            </div>

            <div class="section-card">
                <h3>🛒 المنتجات</h3>
                <p style="color:#c9d1d9;">عناصر منتجات مكتشفة: <b>{products['approx_product_elements_detected']}</b></p>
                {pill(products['has_add_to_cart_button'], 'زر إضافة للسلة')}
                <p style="color:#9aa4b2; margin-top:0.8rem;">{'أمثلة أسعار: ' + '، '.join(products['sample_prices']) if products['sample_prices'] else ''}</p>
            </div>

            <div class="section-card">
                <h3>⏱️ الأداء العام</h3>
                <p style="color:#c9d1d9;">زمن الاستجابة: <b>{response_time:.2f}</b> ثانية &nbsp;|&nbsp; حجم الصفحة: <b>{page_size/1024:.1f}</b> KB</p>
            </div>
            """, unsafe_allow_html=True)

            full_report = {
                "url": url, "scanned_at": datetime.utcnow().isoformat() + "Z",
                "response_time_seconds": round(response_time, 2), "page_size_kb": round(page_size / 1024, 1),
                "scores": scores, "seo": seo, "ux": ux, "products": products, "pagespeed": pagespeed,
            }

            pdf_bytes = build_audit_pdf(full_report)
            col_pdf, col_json = st.columns(2)
            col_pdf.download_button(
                "📄 تحميل تقرير PDF",
                data=pdf_bytes,
                file_name="store_report.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )
            col_json.download_button(
                "⬇️ تحميل JSON (بيانات خام)",
                data=json.dumps(full_report, ensure_ascii=False, indent=2),
                file_name="store_report.json",
                mime="application/json",
                use_container_width=True,
            )


# ==================== تبويب 2: تعديل منتجات سلة ====================
SALLA_AUTH_URL = "https://accounts.salla.sa/oauth2/auth"
SALLA_TOKEN_URL = "https://accounts.salla.sa/oauth2/token"
SALLA_API_BASE = "https://api.salla.dev/admin/v2"


def salla_headers():
    return {"Authorization": f"Bearer {st.session_state['salla_token']}"}


def salla_exchange_code(client_id, client_secret, redirect_uri, code):
    resp = requests.post(SALLA_TOKEN_URL, data={
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
    }, timeout=20)
    resp.raise_for_status()
    return resp.json()


def salla_get_products(page=1):
    resp = requests.get(f"{SALLA_API_BASE}/products", headers=salla_headers(),
                         params={"page": page, "per_page": 20}, timeout=20)
    resp.raise_for_status()
    return resp.json()


def salla_update_product(product_id, payload):
    resp = requests.put(f"{SALLA_API_BASE}/products/{product_id}", headers=salla_headers(),
                         json=payload, timeout=20)
    resp.raise_for_status()
    return resp.json()


def analyze_product_issues(p):
    """يفحص منتج سلة ويرجّع قايمة بمشاكله بالظبط عشان تعرف فين المشكلة."""
    issues = []
    name = (p.get("name") or "").strip()
    if not name:
        issues.append("مفيش اسم للمنتج")
    elif len(name) < 8:
        issues.append("اسم المنتج قصير جداً (أقل من 8 حروف)")

    desc = (p.get("description") or "").strip()
    if not desc:
        issues.append("مفيش وصف للمنتج")
    elif len(re.sub("<[^>]+>", "", desc)) < 30:
        issues.append("الوصف قصير جداً ومش كافي")

    price = (p.get("price") or {}).get("amount")
    if not price or price == 0:
        issues.append("السعر مش متحدد أو صفر")

    qty = p.get("quantity")
    if p.get("unlimited_quantity") is False and (qty is None or qty == 0):
        issues.append("الكمية المتاحة = صفر (المنتج نافد)")

    images = p.get("images") or []
    if not images:
        issues.append("مفيش صور للمنتج")

    if not p.get("categories"):
        issues.append("المنتج مش مربوط بأي تصنيف")

    if p.get("status") and p.get("status") != "sale":
        issues.append(f"حالة المنتج: {p.get('status')} (مش معروض للبيع)")

    return issues


def build_products_issues_pdf(products_with_issues):
    pdf = new_pdf()
    pdf_title(pdf, "تقرير المنتجات المحتاجة تعديل", 18)
    pdf.set_font("Arabic", "", 10)
    pdf.set_text_color(90, 90, 90)
    pdf.multi_cell(0, 7, ar(f"عدد المنتجات: {len(products_with_issues)}"), align="R")
    pdf.ln(3)
    for p, issues in products_with_issues:
        pdf_subtitle(pdf, p.get("name") or "(بدون اسم)")
        for issue in issues:
            pdf_line(pdf, issue, False)
        pdf.ln(2)
    return bytes(pdf.output())


def render_salla_tab():
    hero("🛠️ ربط سلة وتعديل المنتجات", "اربط متجر سلة عشان تقدر تعدّل أسماء وأسعار وكميات المنتجات من هنا مباشرة")

    if "salla_token" not in st.session_state:
        st.session_state["salla_token"] = None

    # التقط كود التفويض من الرابط لو المتجر رجّعه بعد الموافقة
    query_code = st.query_params.get("code")

    with st.expander("⚙️ إعدادات التطبيق (مرة واحدة بس)", expanded=not st.session_state["salla_token"]):
        st.markdown(
            "لازم تكون عامل App على [منصة سلة للمطورين](https://salla.partners) الأول "
            "وناخد منه Client ID و Client Secret، وتحط رابط هذا الموقع نفسه كـ Redirect URI."
        )
        client_id = st.text_input("Client ID", value=st.session_state.get("salla_client_id", ""))
        client_secret = st.text_input("Client Secret", type="password",
                                       value=st.session_state.get("salla_client_secret", ""))
        redirect_uri = st.text_input("Redirect URI (رابط هذا الموقع)",
                                      value=st.session_state.get("salla_redirect_uri", ""))
        st.session_state["salla_client_id"] = client_id
        st.session_state["salla_client_secret"] = client_secret
        st.session_state["salla_redirect_uri"] = redirect_uri

        if client_id and redirect_uri:
            auth_link = (
                f"{SALLA_AUTH_URL}?client_id={client_id}&response_type=code"
                f"&redirect_uri={redirect_uri}&scope=offline_access%20products.read_write"
            )
            st.link_button("🔗 اربط متجر سلة الآن", auth_link, use_container_width=True)

    if query_code and not st.session_state["salla_token"]:
        cid = st.session_state.get("salla_client_id")
        cs = st.session_state.get("salla_client_secret")
        ruri = st.session_state.get("salla_redirect_uri")
        if cid and cs and ruri:
            try:
                token_data = salla_exchange_code(cid, cs, ruri, query_code)
                st.session_state["salla_token"] = token_data.get("access_token")
                st.query_params.clear()
                st.success("✅ تم ربط المتجر بنجاح")
            except requests.RequestException as e:
                st.error(f"فشل استبدال الكود بتوكن: {e}")
        else:
            st.warning("رجّع الكود من سلة، بس لازم تدخل Client ID و Secret و Redirect URI فوق الأول وتضغط الرابط تاني")

    if not st.session_state["salla_token"]:
        st.info("لسه مفيش متجر متصل. افتح الإعدادات فوق واضغط رابط الربط.")
        return

    st.success("متجر متصل ✅")
    if st.button("فك الربط"):
        st.session_state["salla_token"] = None
        st.rerun()

    if st.button("🔄 اجلب المنتجات", type="primary"):
        with st.spinner("جاري جلب المنتجات..."):
            try:
                data = salla_get_products()
                st.session_state["salla_products"] = data.get("data", [])
            except requests.RequestException as e:
                st.error(f"تعذر جلب المنتجات: {e}")

    products = st.session_state.get("salla_products", [])
    if products:
        products_issues = [(p, analyze_product_issues(p)) for p in products]
        need_fix = [(p, issues) for p, issues in products_issues if issues]

        st.markdown(f"### ⚠️ منتجات محتاجة تعديل ({len(need_fix)} من {len(products)})")
        if not need_fix:
            st.success("كل المنتجات سليمة، مفيش مشاكل مكتشفة 🎉")
        else:
            st.download_button(
                "📄 تحميل تقرير المنتجات المحتاجة تعديل PDF",
                data=build_products_issues_pdf(need_fix),
                file_name="products_need_fix.pdf",
                mime="application/pdf",
            )
            for p, issues in need_fix:
                with st.expander(f"⚠️ {p.get('name') or '(بدون اسم)'} — {len(issues)} مشكلة"):
                    for issue in issues:
                        st.write(f"❌ {issue}")
                    st.divider()
                    new_name = st.text_input("الاسم", value=p.get("name", ""), key=f"issue_name_{p['id']}")
                    current_price = (p.get("price") or {}).get("amount", 0) or 0
                    new_price = st.number_input("السعر", value=float(current_price), key=f"issue_price_{p['id']}")
                    new_qty = st.number_input("الكمية المتاحة", value=int(p.get("quantity", 0) or 0),
                                               key=f"issue_qty_{p['id']}")
                    if st.button("💾 حفظ التعديل", key=f"issue_save_{p['id']}"):
                        try:
                            salla_update_product(p["id"], {
                                "name": new_name, "price": new_price, "quantity": new_qty,
                            })
                            st.success("تم الحفظ ✅")
                        except requests.RequestException as e:
                            st.error(f"فشل الحفظ: {e}")

        st.markdown(f"### 🗂️ كل المنتجات ({len(products)})")
        for p, issues in products_issues:
            mark = "⚠️ " if issues else "✅ "
            with st.expander(f"{mark}{p.get('name')} — {p.get('price', {}).get('amount', '')} {p.get('price', {}).get('currency', '')}"):
                new_name = st.text_input("الاسم", value=p.get("name", ""), key=f"name_{p['id']}")
                current_price = p.get("price", {}).get("amount", 0)
                new_price = st.number_input("السعر", value=float(current_price), key=f"price_{p['id']}")
                new_qty = st.number_input("الكمية المتاحة", value=int(p.get("quantity", 0) or 0),
                                           key=f"qty_{p['id']}")
                if st.button("💾 حفظ التعديل", key=f"save_{p['id']}"):
                    try:
                        salla_update_product(p["id"], {
                            "name": new_name, "price": new_price, "quantity": new_qty,
                        })
                        st.success("تم الحفظ ✅")
                    except requests.RequestException as e:
                        st.error(f"فشل الحفظ: {e}")


# ==================== نقطة البداية ====================
tab1, tab2 = st.tabs(["🔍 فحص المتجر", "🛠️ تعديل منتجات سلة"])
with tab1:
    render_audit_tab()
with tab2:
    render_salla_tab()
