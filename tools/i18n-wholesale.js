const translations = {
  "en": {
    "back_home": "← Back to Home",
    "p_badge": "Wholesale Benchmarking Engine v1.0",
    "title": "2026 Wholesale Cost Benchmarker",
    "subtitle": "Compare your ingredient costs with UK regional averages and receive AI-driven inflation warnings.",
    "live_data": "Live Data Hub · March 2026 Baseline",
    "how_to_use": "Select your region and input your current wholesale prices for Jasmine Rice (10kg bag) and Vegetable Oil (20L container). The tool will compare your prices against regional averages, show potential annual savings, and visualize where you stand.",
    "card_input": "Price Input & Analysis",
    "card_viz": "Price Comparison Visualization",
    "card_heatmap": "Regional Price Heatmap",
    "card_annual": "Annual Cost & Leakage Analysis",
    "card_ai": "AI Market Insights & Inflation Warnings",
    "card_faq": "UK Thai Wholesale Intelligence FAQ",
    "label_region": "Your Current Region",
    "label_rice": "Your Price for 10kg Jasmine Rice",
    "label_oil": "Your Price for 20L Vegetable Oil",
    "btn_analyze": "Analyze My Prices",
    "res_regional_avg": "vs. Regional Average",
    "res_uk_best": "vs. UK Best Price",
    "res_savings": "Potential Annual Savings",
    "res_your_annual": "Your Annual Cost",
    "res_avg_annual": "Cost at Regional Avg",
    "res_best_annual": "Cost at UK Best Price",
    "res_diff": "Price Difference",
    "res_usage": "Based on your usage",
    "res_combined": "Rice & Oil combined",
    "res_pot_savings": "Potential savings",
    "res_max_savings": "Maximum savings"
  },
  "th": {
    "back_home": "← กลับหน้าหลัก",
    "p_badge": "ระบบวัดมาตรฐานการจัดซื้อขายส่ง รุ่น 1.0",
    "title": "ตัววัดมาตรฐานต้นทุนขายส่ง 2569",
    "subtitle": "เปรียบเทียบต้นทุนวัตถุดิบกับค่าเฉลี่ยระดับภูมิภาคในสหราชอาณาจักร และรับการแจ้งเตือนภาวะเงินเฟ้อด้วย AI",
    "live_data": "ศูนย์ข้อมูลสด · ฐานข้อมูลมีนาคม 2569",
    "how_to_use": "เลือกภูมิภาคของคุณและป้อนราคาขายส่งปัจจุบันสำหรับข้าวหอมมะลิ (ถุง 10 กก.) และน้ำมันพืช (ภาชนะ 20 ลิตร) เครื่องมือจะเปรียบเทียบราคาของคุณกับค่าเฉลี่ยภูมิภาค แสดงโอกาสประหยัดรายปี และวิเคราะห์เป้าหมายของคุณ",
    "card_input": "ป้อนข้อมูลและวิเคราะห์ราคา",
    "card_viz": "ภาพเปรียบเทียบราคา",
    "card_heatmap": "แผนที่แสดงความแตกต่างราคาระดับภูมิภาค",
    "card_annual": "วิเคราะห์ต้นทุนรายปีและจุดรั่วไหล",
    "card_ai": "ข้อมูลตลาดจาก AI และการแจ้งเตือนเงินเฟ้อ",
    "card_faq": "คำถามพบบ่อยเกี่ยวกับข้อมูลขายส่งในอังกฤษ",
    "label_region": "ภูมิภาคที่ตั้งร้านของคุณ",
    "label_rice": "ราคาข้าวหอมมะลิ (10 กก.) ของคุณ",
    "label_oil": "ราคาน้ำมันพืช (20 ลิตร) ของคุณ",
    "btn_analyze": "วิเคราะห์ราคาของฉัน",
    "res_regional_avg": "เทียบกับราคาเฉลี่ยภูมิภาค",
    "res_uk_best": "เทียบกับราคาดีที่สุดในอังกฤษ",
    "res_savings": "โอกาสประหยัดรายปี",
    "res_your_annual": "ต้นทุนรายปีของคุณ",
    "res_avg_annual": "ต้นทุนที่ราคาเฉลี่ยภูมิภาค",
    "res_best_annual": "ต้นทุนที่ราคาดีที่สุดในอังกฤษ",
    "res_diff": "ส่วนต่างราคา",
    "res_usage": "จากอัตราการใช้งานของคุณ",
    "res_combined": "ข้าวและน้ำมันรวมกัน",
    "res_pot_savings": "โอกาสประหยัดที่คาดการณ์",
    "res_max_savings": "โอกาสประหยัดสูงสุด"
  }
};

/**
 * Sets the UI language by applying translations to all [data-i18n] elements
 * and persisting the selection to localStorage. Re-runs analysis on change.
 * @param {string} lang - Language code ("en" or "th")
 */
function setLanguage(lang) {
  localStorage.setItem('thaidata_lang', lang);
  document.documentElement.lang = lang;
  
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.getAttribute('data-i18n');
    if (translations[lang][key]) {
      el.textContent = translations[lang][key];
    }
  });

  // Re-run analysis to update charts and dynamic text
  if (typeof performAnalysis === 'function') {
    performAnalysis();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const savedLang = localStorage.getItem('thaidata_lang') || 'en';
  setLanguage(savedLang);
});
