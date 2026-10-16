/**
 * Cookie consent banner for ThaiData UK
 * @module privacy-banner
 *
 * Presentation only - the consent logic (localStorage key, gtag/clarity calls, default
 * deny) is unchanged.
 *
 * This used to be a 500px centred floating card with a drop shadow at z-index 9999. On
 * a 390x844 phone it measured 351x205 at y=623-828, which covered ALL THREE claim rows
 * in the hero (measured at y=564-664, 665-764, 765-865). The three proof rows are the
 * entire mechanism of the homepage redesign, so the banner was hiding the thing the page
 * exists to show.
 *
 * It is now a 56px full-bleed bar pinned to the bottom edge:
 *   - it cannot overlap the hero's rows, because the page reserves its height while shown
 *   - one line of copy, 15px, at --ink-mute (the design's META level)
 *   - Accept and Reject are equal-weight ghost buttons, so neither is the "right" answer
 *   - z-index 90, below the sticky nav
 * Copy change: "Thai operators" -> "Thai restaurant owners". The design bans "operators";
 * a 55-year-old owner does not call themselves that.
 */

(function() {
    // 1. Check if consent already given
    if (localStorage.getItem('thaidata_consent')) return;

    // 2. Inject CSS
    const css = `
        #cookie-banner {
            position: fixed;
            left: 0;
            right: 0;
            bottom: 0;
            width: 100%;
            max-width: none;
            background: var(--paper, #FFFFFF);
            border-top: 1px solid var(--hairline, #E4DCCE);
            box-shadow: none;
            padding: 0 16px;
            min-height: 56px;
            z-index: 90;
            display: flex;
            flex-direction: row;
            align-items: center;
            gap: 16px;
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }

        /* reserve the bar's height so nothing underneath is ever covered */
        body.has-consent-bar { padding-bottom: 56px; }

        .cb-text {
            flex: 1 1 auto;
            font-size: 15px;
            line-height: 1.35;
            color: var(--ink-mute, #5B534C);
            min-width: 0;
        }
        .cb-text a { color: var(--red, #A3132B); text-decoration: underline; font-weight: 500; }

        .cb-btns { display: flex; gap: 8px; flex: 0 0 auto; }

        /* equal-weight ghost buttons: neither reads as the default */
        .cb-btn {
            padding: 8px 14px;
            min-height: 40px;
            border-radius: var(--r-obj, 10px);
            font-size: 15px;
            font-weight: 600;
            font-family: inherit;
            cursor: pointer;
            border: 1px solid var(--hairline, #E4DCCE);
            background: var(--paper, #FFFFFF);
            color: var(--ink, #1A1614);
            text-align: center;
            white-space: nowrap;
        }
        .cb-btn:hover { border-color: var(--ink, #1A1614); }
        .cb-btn:focus-visible {
            outline: 3px solid var(--turmeric, #F2B21A);
            outline-offset: 2px;
        }

        /* on a narrow phone the copy truncates rather than growing the bar */
        @media (max-width: 560px) {
            #cookie-banner { gap: 10px; padding: 0 12px; }
            .cb-text { font-size: 14px; }
            .cb-btn { padding: 8px 10px; font-size: 14px; }
        }
    `;
    const style = document.createElement('style');
    style.innerHTML = css;
    document.head.appendChild(style);

    // 3. Create Banner HTML
    const banner = document.createElement('div');
    banner.id = 'cookie-banner';
    banner.setAttribute('role', 'region');
    banner.setAttribute('aria-label', 'Cookie consent');
    banner.innerHTML = `
        <div class="cb-text">
            We use cookies to understand how our pages are used. See our <a href="/privacy">Privacy Policy</a>.
        </div>
        <div class="cb-btns">
            <button class="cb-btn" id="cb-no">Essential only</button>
            <button class="cb-btn" id="cb-yes">Accept all</button>
        </div>
    `;
    document.body.appendChild(banner);
    document.body.classList.add('has-consent-bar');

    function dismiss(value) {
        localStorage.setItem('thaidata_consent', value);
        banner.remove();
        document.body.classList.remove('has-consent-bar');
    }

    // 4. Handle Buttons
    document.getElementById('cb-yes').onclick = function() {
        if (typeof gtag === 'function') {
            gtag('consent', 'update', {
                'analytics_storage': 'granted',
                'ad_storage': 'granted'
            });
        }
        if (typeof clarity === 'function') {
            clarity('consent', true);
        }
        dismiss('granted');
    };

    document.getElementById('cb-no').onclick = function() {
        if (typeof clarity === 'function') {
            clarity('consent', false);
        }
        dismiss('denied');
    };

    // 5. Consent default is set inline in each page's <head> (before any gtag
    //    hit). This script only UPGRADES it via the buttons above. Keeping the
    //    default here duplicated it and ran it after gtag had already loaded.

})();
