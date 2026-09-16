import json
import re
from datetime import datetime
from urllib.parse import urlparse

import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(page_title="فاحص المتاجر", page_icon="🔍", layout="centered")

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


# ---------------- UI ----------------
st.title("🔍 فاحص المتاجر الإلكترونية")
st.caption("حط رابط أي متجر واحصل على تقرير SEO وتجربة استخدام ومنتجات في ثواني")

with st.form("audit_form"):
    url = st.text_input("رابط المتجر", placeholder="https://example-store.com")
    api_key = st.text_input("مفتاح PageSpeed API (اختياري - لدرجة السرعة)", type="password")
    submitted = st.form_submit_button("افحص المتجر", use_container_width=True, type="primary")

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

        col1, col2, col3 = st.columns(3)
        col1.metric("SEO", f"{scores['seo_score']}/100")
        col2.metric("UX", f"{scores['ux_score']}/100")
        col3.metric("السرعة", f"{scores['speed_score']}/100" if scores['speed_score'] is not None else "—")

        st.markdown("### 🔍 SEO")
        st.write(f"{badge(seo['title_ok'])} العنوان: {seo['title'] or 'غير موجود'}")
        st.write(f"{badge(seo['meta_description_ok'])} الوصف الميتا")
        st.write(f"{badge(seo['h1_ok'])} H1 (عدد: {seo['h1_count']})")
        st.write(f"{badge(seo['has_structured_data'])} Structured Data")
        st.write(f"{badge(seo['has_open_graph'])} Open Graph")
        st.write(f"{badge(seo['sitemap_found'])} Sitemap")
        st.write(f"🖼️ صور بدون alt text: {seo['images_missing_alt']}/{seo['total_images']}")

        st.markdown("### 🎨 تجربة المستخدم")
        st.write(f"{badge(ux['uses_https'])} HTTPS")
        st.write(f"{badge(ux['has_search_box'])} خانة بحث")
        st.write(f"{badge(ux['has_cart_icon'])} سلة واضحة")
        st.write(f"{badge(ux['has_whatsapp_or_chat'])} واتساب / شات")

        st.markdown("### 🛒 المنتجات")
        st.write(f"عناصر منتجات مكتشفة: {products['approx_product_elements_detected']}")
        st.write(f"{badge(products['has_add_to_cart_button'])} زر إضافة للسلة")
        if products["sample_prices"]:
            st.write("أمثلة أسعار: " + ", ".join(products["sample_prices"]))

        st.markdown("### ⏱️ الأداء العام")
        st.write(f"زمن الاستجابة: {response_time:.2f} ثانية")
        st.write(f"حجم الصفحة: {page_size/1024:.1f} KB")

        full_report = {
            "url": url, "scanned_at": datetime.utcnow().isoformat() + "Z",
            "scores": scores, "seo": seo, "ux": ux, "products": products, "pagespeed": pagespeed,
        }
        st.download_button(
            "⬇️ تحميل التقرير الكامل (JSON)",
            data=json.dumps(full_report, ensure_ascii=False, indent=2),
            file_name="store_report.json",
            mime="application/json",
            use_container_width=True,
        )
