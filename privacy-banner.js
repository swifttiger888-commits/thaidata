/**
 * Cookie consent banner for ThaiData UK
 * @module privacy-banner
 */

(function() {
    // 1. Check if consent already given
    if (localStorage.getItem('thaidata_consent')) return;

    // 2. Inject CSS
    const css = `
        #cookie-banner {
            position: fixed;
            bottom: 24px;
            left: 50%;
            transform: translateX(-50%);
            width: 90%;
            max-width: 500px;
            background: #ffffff;
            border: 1px solid #E5E7EB;
            border-radius: 16px;
            padding: 24px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.1), 0 8px 10px -6px rgba(0, 0, 0, 0.1);
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 16px;
            animation: slideUp 0.5s ease-out;
            font-family: 'Inter', system-ui, sans-serif;
        }

        @keyframes slideUp {
            from { transform: translate(-50%, 100%); opacity: 0; }
            to { transform: translate(-50%, 0); opacity: 1; }
        }

        .cb-text { font-size: 0.9rem; color: #374151; line-height: 1.5; }
        .cb-text a { color: #0A7A6F; text-decoration: underline; font-weight: 500; }
        
        .cb-btns { display: flex; gap: 12px; }
        .cb-btn { 
            flex: 1; 
            padding: 10px 16px; 
            border-radius: 8px; 
            font-size: 0.85rem; 
            font-weight: 600; 
            cursor: pointer; 
            transition: all 0.2s;
            border: none;
            text-align: center;
        }
        .cb-accept { background: #0A7A6F; color: white; }
        .cb-accept:hover { background: #065F56; }
        .cb-decline { background: #F3F4F6; color: #4B5563; }
        .cb-decline:hover { background: #E5E7EB; }

        @media (max-width: 480px) {
            #cookie-banner { bottom: 16px; padding: 20px; }
            .cb-btns { flex-direction: column; }
        }
    `;
    const style = document.createElement('style');
    style.innerHTML = css;
    document.head.appendChild(style);

    // 3. Create Banner HTML
    const banner = document.createElement('div');
    banner.id = 'cookie-banner';
    banner.innerHTML = `
        <div class="cb-text">
            We use cookies to understand how you use our tools and to improve the experience for Thai operators. See our <a href="/privacy.html">Privacy Policy</a>.
        </div>
        <div class="cb-btns">
            <button class="cb-btn cb-decline" id="cb-no">Essential Only</button>
            <button class="cb-btn cb-accept" id="cb-yes">Accept All</button>
        </div>
    `;
    document.body.appendChild(banner);

    // 4. Handle Buttons
    document.getElementById('cb-yes').onclick = function() {
        localStorage.setItem('thaidata_consent', 'granted');
        if (typeof gtag === 'function') {
            gtag('consent', 'update', { 
                'analytics_storage': 'granted',
                'ad_storage': 'granted'
            });
        }
        banner.remove();
    };

    document.getElementById('cb-no').onclick = function() {
        localStorage.setItem('thaidata_consent', 'denied');
        banner.remove();
    };

    // 5. Default Consent State (Deny until accepted)
    if (typeof gtag === 'function') {
        gtag('consent', 'default', {
            'analytics_storage': 'denied',
            'ad_storage': 'denied'
        });
    }

})();
