// ThaiData UK — _email.js (shared email module)
// Single source of truth for all transactional emails.
// Used by: admin.js, listing.js, claim.js, correction.js
//
// ── Email log table ──
// Created on first use. Fields:
//   id, email_type, recipient, restaurant_name, claim_id, subject,
//   status ('sending'|'sent'|'failed'), resend_id, resend_status, error, created_at

/**
 * Computes SHA-256 hex digest of a string (single copy — DRY).
 */
export async function sha256(text) {
  const encoder = new TextEncoder();
  const data = encoder.encode(text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('');
}

/**
 * Core transport — logs attempt to email_log, calls Resend, updates log.
 * All other functions in this module route through this one.
 */
async function sendEmail(env, { to, subject, html, emailType, claimId, restaurantName, replyTo }) {
  // Ensure email_log table exists (same pattern as login_attempts in admin.js)
  await env.DB.prepare(
    `CREATE TABLE IF NOT EXISTS email_log (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      email_type TEXT NOT NULL,
      recipient TEXT NOT NULL,
      restaurant_name TEXT,
      claim_id INTEGER,
      subject TEXT,
      status TEXT NOT NULL DEFAULT 'sending',
      resend_id TEXT,
      resend_status INTEGER,
      error TEXT,
      created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )`
  ).run();

  // Insert log row BEFORE calling Resend
  const logResult = await env.DB.prepare(
    `INSERT INTO email_log (email_type, recipient, restaurant_name, claim_id, subject, status)
     VALUES (?, ?, ?, ?, ?, 'sending')`
  ).bind(emailType, to, restaurantName || null, claimId || null, subject).run();
  const logId = logResult.meta.last_row_id;

  const apiKey = env.RESEND_API_KEY;
  if (!apiKey) {
    await env.DB.prepare(
      'UPDATE email_log SET status = ?, error = ? WHERE id = ?'
    ).bind('failed', 'Missing RESEND_API_KEY', logId).run();
    console.error(`Missing RESEND_API_KEY — cannot send ${emailType}`);
    return { success: false, error: 'Missing RESEND_API_KEY', logId };
  }

  const replyToEmail = replyTo || env.ADMIN_EMAIL || 'hello@thaidata.uk';

  try {
    const res = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: 'ThaiData UK <hello@thaidata.uk>',
        reply_to: replyToEmail,
        to: [to],
        subject,
        html,
      }),
    });

    if (!res.ok) {
      const errBody = await res.text();
      await env.DB.prepare(
        'UPDATE email_log SET status = ?, error = ?, resend_status = ? WHERE id = ?'
      ).bind('failed', errBody, res.status, logId).run();
      console.error(`Resend API error ${res.status}: ${errBody}`);
      return { success: false, error: errBody, logId };
    }

    const data = await res.json();
    await env.DB.prepare(
      'UPDATE email_log SET status = ?, resend_id = ? WHERE id = ?'
    ).bind('sent', data.id || null, logId).run();
    console.log(`${emailType} email sent to ${to} (Resend ${data.id})`);
    return { success: true, resendId: data.id, logId };

  } catch (err) {
    await env.DB.prepare(
      'UPDATE email_log SET status = ?, error = ? WHERE id = ?'
    ).bind('failed', err.message, logId).run();
    console.error('Resend send failed:', err.message);
    return { success: false, error: err.message, logId };
  }
}

// ═══════════════════════════════════════════════════════════════
// Template builders (inline HTML — no external template deps)
// ═══════════════════════════════════════════════════════════════

function emailShell({ heroTitle, heroSubtitleHtml, bodyHtml, footerHtml }) {
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0;padding:0;background-color:#f5f5f0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f0;padding:40px 0;">
    <tr>
      <td align="center">
        <table width="560" cellpadding="0" cellspacing="0" style="max-width:560px;width:100%;">
          <tr>
            <td style="padding:32px 40px 0;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:linear-gradient(135deg,#A3132B,#7E0E20);border-radius:12px;">
                <tr>
                  <td style="padding:32px 32px 24px;text-align:center;">
                    <img src="https://thaidata.uk/static/logo-email.png" width="180" height="72" alt="ThaiData UK" style="display:block;border:0;outline:none;margin:0 auto 20px;">
                    <h1 style="margin:0 0 8px;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">${heroTitle}</h1>
                    <p style="margin:0;color:rgba(255,255,255,0.9);font-size:15px;line-height:1.5;">${heroSubtitleHtml}</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 40px 32px;">
              <table width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;border:1px solid #e8e8dc;">
                <tr>
                  <td style="padding:32px;">
                    ${bodyHtml}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          ${footerHtml}
        </table>
      </td>
    </tr>
  </table>
</body>
</html>`;
}

// ── Magic link email (approval — Flow 2) ──
function buildMagicLinkApprovalHtml({ restaurant_name, city, magicLink }) {
  return emailShell({
    heroTitle: 'Your Listing Is Ready!',
    heroSubtitleHtml: `${restaurant_name}<br><span style="font-size:13px;opacity:0.7;">${city}</span>`,
    bodyHtml: `
                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">
                      Great news — your claim for ${restaurant_name} has been approved! 🎉
                    </p>
                    <p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">
                      Here's your one-time magic link to edit your ThaiData listing:
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td align="center">
                          <a href="${magicLink}" style="display:inline-block;background:#A3132B;color:#ffffff;padding:14px 44px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:600;">Edit My Listing →</a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:24px 0 0;color:#999;font-size:12px;line-height:1.5;text-align:center;">
                      This link expires in 1 hour and can only be used once.<br>
                      If you didn't request this, you can safely ignore this email.
                    </p>`,
    footerHtml: `
          <tr>
            <td style="padding:0 40px 32px;text-align:center;">
              <p style="margin:0;color:#aaa;font-size:11px;line-height:1.6;">
                ThaiData UK · The UK's Thai restaurant directory<br>
                <a href="https://thaidata.uk" style="color:#A3132B;text-decoration:none;">thaidata.uk</a>
              </p>
            </td>
          </tr>`,
  });
}

// ── Magic link email (self-service re-request — Flow 5) ──
function buildMagicLinkSelfServiceHtml({ restaurant_name, city, magicLink }) {
  return emailShell({
    heroTitle: 'Manage Your Listing',
    heroSubtitleHtml: `${restaurant_name}<br><span style="font-size:13px;opacity:0.7;">${city}</span>`,
    bodyHtml: `
                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">
                      You're one click away from editing your restaurant listing on ThaiData UK — the UK's fastest-growing Thai restaurant directory.
                    </p>
                    <p style="margin:0 0 20px;color:#555;font-size:14px;line-height:1.6;">
                      What you can update:
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
                      <tr>
                        <td style="padding:5px 0;color:#444;font-size:14px;">✓ Photos, description &amp; cuisine specialities</td>
                      </tr>
                      <tr>
                        <td style="padding:5px 0;color:#444;font-size:14px;">✓ Opening hours, website &amp; social links</td>
                      </tr>
                      <tr>
                        <td style="padding:5px 0;color:#444;font-size:14px;">✓ Contact details &amp; price range</td>
                      </tr>
                    </table>
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td align="center">
                          <a href="${magicLink}" style="display:inline-block;background:#A3132B;color:#ffffff;padding:14px 44px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:600;">Edit My Listing →</a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:24px 0 0;color:#999;font-size:12px;line-height:1.5;text-align:center;">
                      This link expires in 1 hour and can only be used once.<br>
                      If you didn't request this, you can safely ignore this email.
                    </p>`,
    footerHtml: `
          <tr>
            <td style="padding:0 40px 32px;text-align:center;">
              <p style="margin:0;color:#aaa;font-size:11px;line-height:1.6;">
                ThaiData UK · The UK's Thai restaurant directory<br>
                <a href="https://thaidata.uk" style="color:#A3132B;text-decoration:none;">thaidata.uk</a>
              </p>
            </td>
          </tr>`,
  });
}

// ── Recovery email (Flow 4 — FIXED: distinct from approval) ──
function buildRecoveryHtml({ restaurant_name, city, magicLink }) {
  return emailShell({
    heroTitle: 'Your Recovery Link',
    heroSubtitleHtml: `${restaurant_name}<br><span style="font-size:13px;opacity:0.7;">${city}</span>`,
    bodyHtml: `
                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">
                      Here's a new magic link to manage your listing for ${restaurant_name}.
                    </p>
                    <p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">
                      Your previous link may have expired or been lost. Use this one to edit your listing:
                    </p>
                    <table width="100%" cellpadding="0" cellspacing="0">
                      <tr>
                        <td align="center">
                          <a href="${magicLink}" style="display:inline-block;background:#A3132B;color:#ffffff;padding:14px 44px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:600;">Edit My Listing →</a>
                        </td>
                      </tr>
                    </table>
                    <p style="margin:24px 0 0;color:#999;font-size:12px;line-height:1.5;text-align:center;">
                      This link expires in 1 hour and can only be used once.<br>
                      If you didn't request this, you can safely ignore this email.
                    </p>`,
    footerHtml: `
          <tr>
            <td style="padding:0 40px 32px;text-align:center;">
              <p style="margin:0;color:#aaa;font-size:11px;line-height:1.6;">
                ThaiData UK · The UK's Thai restaurant directory<br>
                <a href="https://thaidata.uk" style="color:#A3132B;text-decoration:none;">thaidata.uk</a>
              </p>
            </td>
          </tr>`,
  });
}

// ── Claim confirmation (Flow 1) ──
function buildClaimConfirmationHtml({ claimer_name, restaurant_name, city }) {
  return emailShell({
    heroTitle: 'Claim Received',
    heroSubtitleHtml: `${restaurant_name} &middot; ${city}`,
    bodyHtml: `
                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">Hi ${claimer_name},</p>
                    <p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">We&rsquo;ve received your claim for <strong>${restaurant_name}</strong> in ${city}.</p>
                    <p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">We&rsquo;ll review your details and, if everything looks good, send you a one&shy;time magic link so you can edit your ThaiData listing.</p>
                    <p style="margin:0 0 24px;color:#555;font-size:14px;line-height:1.6;">You don&rsquo;t need to do anything else right now. If you made this request by mistake, you can ignore this email.</p>
                    <p style="margin:0;color:#555;font-size:14px;line-height:1.6;">Thanks,<br>The ThaiData team</p>`,
    footerHtml: `
          <tr>
            <td style="padding:0 40px 32px;text-align:center;">
              <p style="margin:0;color:#aaa;font-size:11px;">ThaiData UK &middot; <a href="https://thaidata.uk" style="color:#A3132B;text-decoration:none;">thaidata.uk</a></p>
            </td>
          </tr>`,
  });
}

// ── Claim rejection (Flow 3) ──
function buildClaimRejectedHtml({ claimer_name, restaurant_name, city }) {
  return emailShell({
    heroTitle: 'Claim Update',
    heroSubtitleHtml: `${restaurant_name}<br><span style="font-size:13px;opacity:0.7;">${city}</span>`,
    bodyHtml: `
                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">
                      Hi ${claimer_name},</p>
                    <p style="margin:0 0 16px;color:#555555;font-size:14px;line-height:1.6;">
                      Thank you for your interest in claiming <strong>${restaurant_name}</strong> on ThaiData UK.
                    </p>
                    <p style="margin:0 0 16px;color:#555555;font-size:14px;line-height:1.6;">
                      After reviewing your submission, we were unable to verify your connection to this restaurant. As a result, your claim was not approved on this occasion.
                    </p>
                    <p style="margin:0 0 16px;color:#555555;font-size:14px;line-height:1.6;">
                      If you believe this was a mistake and can provide additional verification (such as a document showing your association with the restaurant), please reply to this email and we'll take another look.
                    </p>
                    <p style="margin:0;color:#555;font-size:14px;line-height:1.6;">Thanks,<br>The ThaiData team</p>`,
    footerHtml: `
          <tr>
            <td style="padding:0 40px 32px;text-align:center;">
              <p style="margin:0;color:#aaa;font-size:11px;">ThaiData UK &middot; <a href="https://thaidata.uk" style="color:#A3132B;text-decoration:none;">thaidata.uk</a></p>
            </td>
          </tr>`,
  });
}

// ═══════════════════════════════════════════════════════════════
// Public API — called by route handlers
// ═══════════════════════════════════════════════════════════════

/**
 * Magic link email — two variants:
 *   'approval'     → auto-sent when admin approves a claim (Flow 2)
 *   'self_service' → owner re-requests from /listing/manage (Flow 5)
 */
export async function sendMagicLinkEmail(env, { email, restaurant_name, city, magicLink, claimId, variant = 'approval' }) {
  const subject = variant === 'self_service'
    ? `🔑 Your magic link for ${restaurant_name}`
    : `🎉 Your listing is ready — ${restaurant_name}`;

  const html = variant === 'self_service'
    ? buildMagicLinkSelfServiceHtml({ restaurant_name, city, magicLink })
    : buildMagicLinkApprovalHtml({ restaurant_name, city, magicLink });

  const emailType = variant === 'self_service'
    ? 'magic_link_self_service'
    : 'magic_link_approval';

  return sendEmail(env, {
    to: email,
    subject,
    html,
    emailType,
    claimId,
    restaurantName: restaurant_name,
  });
}

/**
 * Recovery email (Flow 4) — distinct from approval.
 * Used when admin changes the claimer email on an approved claim.
 */
export async function sendRecoveryEmail(env, { email, restaurant_name, city, magicLink, claimId }) {
  const subject = `🔑 Your ThaiData recovery link for ${restaurant_name}`;
  const html = buildRecoveryHtml({ restaurant_name, city, magicLink });

  return sendEmail(env, {
    to: email,
    subject,
    html,
    emailType: 'recovery',
    claimId,
    restaurantName: restaurant_name,
  });
}

/**
 * Claim confirmation (Flow 1) — sent when claim form is submitted.
 */
export async function sendClaimConfirmationEmail(env, { claimer_name, claimer_email, restaurant_name, city, claimId }) {
  const subject = `We\u2019ve received your claim for ${restaurant_name}`;
  const html = buildClaimConfirmationHtml({ claimer_name, restaurant_name, city });

  return sendEmail(env, {
    to: claimer_email,
    subject,
    html,
    emailType: 'claim_confirmation',
    claimId,
    restaurantName: restaurant_name,
  });
}

/**
 * Claim rejection (Flow 3) — sent when admin rejects a claim.
 */
export async function sendClaimRejectedEmail(env, { claimer_name, claimer_email, restaurant_name, city, claimId }) {
  const subject = `Update on your ThaiData claim for ${restaurant_name}`;
  const html = buildClaimRejectedHtml({ claimer_name, restaurant_name, city });

  return sendEmail(env, {
    to: claimer_email,
    subject,
    html,
    emailType: 'claim_rejected',
    claimId,
    restaurantName: restaurant_name,
  });
}

/**
 * Admin notification — sent to hello@thaidata.uk when a new claim is submitted
 */
export async function sendAdminClaimNotification(env, { id, restaurant_name, city, claimer_name, claimer_email, claimer_phone, claimer_role, business_type }) {
  const subject = `🔔 New claim #${id} — ${restaurant_name}, ${city}`;
  const role = claimer_role === 'owner' ? 'Owner' : claimer_role === 'manager' ? 'Manager' : claimer_role === 'head_chef' ? 'Head Chef' : 'Staff';
  const businessType = business_type === 'takeaway' ? 'Takeaway' : 'Restaurant';
  const phoneLine = claimer_phone ? `\n📞 ${claimer_phone}` : '';

  const html = `<p style="font-size:15px;line-height:1.6;margin:0 0 16px;">New claim submitted.</p>
<table style="font-size:14px;line-height:1.8;margin:0 0 16px;border-collapse:collapse;">
  <tr><td style="padding:4px 12px 4px 0;color:#666;">Restaurant:</td><td style="padding:4px 0;font-weight:600;">${restaurant_name}</td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#666;">City:</td><td style="padding:4px 0;">${city}</td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#666;">Type:</td><td style="padding:4px 0;">${businessType}</td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#666;">Claimant:</td><td style="padding:4px 0;">${claimer_name}</td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#666;">Email:</td><td style="padding:4px 0;"><a href="mailto:${claimer_email}" style="color:#A3132B;">${claimer_email}</a></td></tr>
  <tr><td style="padding:4px 12px 4px 0;color:#666;">Role:</td><td style="padding:4px 0;">${role}</td></tr>${phoneLine ? `<tr><td style="padding:4px 12px 4px 0;color:#666;">Phone:</td><td style="padding:4px 0;">${claimer_phone}</td></tr>` : ''}
</table>
<p style="margin:20px 0 0;"><a href="https://thaidata.uk/admin/" style="display:inline-block;background:#A3132B;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-size:14px;font-weight:600;">Review in Admin →</a></p>`;

  return sendEmail(env, {
    to: 'hello@thaidata.uk',
    subject,
    html,
    emailType: 'admin_claim_notification',
    claimId: id,
    restaurantName: restaurant_name,
  });
}

// ═══════════════════════════════════════════════════════════════
// Correction reports (owner-help report form on /r/ pages)
// ═══════════════════════════════════════════════════════════════

/** Minimal HTML escape for user-supplied text in emails. */
function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

const CORRECTION_CATEGORY_LABELS = {
  hours: 'Opening hours',
  address: 'Address / location',
  contact: 'Phone / website',
  closed: 'Permanently closed',
  menu: 'Menu / prices',
  other: 'Other',
};

function buildCorrectionNotificationHtml({ id, restaurant_name, city, category, details, reporter_email, page_url }) {
  const label = CORRECTION_CATEGORY_LABELS[category] || category;
  const reporterLine = reporter_email
    ? `<p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">Reporter email: <a href="mailto:${esc(reporter_email)}" style="color:#A3132B;">${esc(reporter_email)}</a></p>`
    : `<p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">No reporter email provided.</p>`;
  const pageLine = (page_url && page_url.startsWith('/'))
    ? `<p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">Page: <a href="https://thaidata.uk${esc(page_url)}" style="color:#A3132B;">https://thaidata.uk${esc(page_url)}</a></p>`
    : '';
  return emailShell({
    heroTitle: 'Correction Report',
    heroSubtitleHtml: `${esc(restaurant_name)} &middot; ${esc(city)}`,
    bodyHtml: `
                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">Report #${id} — ${esc(label)}</p>
                    <p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;white-space:pre-wrap;">${esc(details)}</p>
                    ${reporterLine}
                    ${pageLine}`,
    footerHtml: `
          <tr>
            <td style="padding:0 40px 32px;text-align:center;">
              <p style="margin:0;color:#aaa;font-size:11px;">ThaiData UK &middot; <a href="https://thaidata.uk" style="color:#A3132B;text-decoration:none;">thaidata.uk</a></p>
            </td>
          </tr>`,
  });
}

/** Notifies the admin inbox about a new correction report (reply-to = reporter when given). */
export async function sendCorrectionNotification(env, report) {
  const label = CORRECTION_CATEGORY_LABELS[report.category] || report.category;
  const subject = `Correction report — ${report.restaurant_name} (${report.city}) — ${label}`;
  return sendEmail(env, {
    to: env.ADMIN_EMAIL || 'hello@thaidata.uk',
    subject,
    html: buildCorrectionNotificationHtml(report),
    emailType: 'correction_notification',
    restaurantName: report.restaurant_name,
    replyTo: report.reporter_email || undefined,
  });
}

function buildCorrectionAckHtml({ restaurant_name, city }) {
  return emailShell({
    heroTitle: 'Report Received',
    heroSubtitleHtml: `${esc(restaurant_name)} &middot; ${esc(city)}`,
    bodyHtml: `
                    <p style="margin:0 0 16px;color:#1a1a1a;font-size:15px;line-height:1.6;">Hi,</p>
                    <p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">Thanks for flagging something on our page for <strong>${esc(restaurant_name)}</strong>. We&rsquo;ve logged your report and a human will check it — usually within a few hours.</p>
                    <p style="margin:0 0 16px;color:#555;font-size:14px;line-height:1.6;">We don&rsquo;t change anything automatically: every report is reviewed first. If we need more detail, we&rsquo;ll reply to this email.</p>
                    <p style="margin:0;color:#555;font-size:14px;line-height:1.6;">Thanks,<br>The ThaiData team</p>`,
    footerHtml: `
          <tr>
            <td style="padding:0 40px 32px;text-align:center;">
              <p style="margin:0;color:#aaa;font-size:11px;">ThaiData UK &middot; <a href="https://thaidata.uk" style="color:#A3132B;text-decoration:none;">thaidata.uk</a></p>
            </td>
          </tr>`,
  });
}

/** Acknowledges a correction report to the reporter. */
export async function sendCorrectionAck(env, { to, restaurant_name, city }) {
  return sendEmail(env, {
    to,
    subject: `We've got your report — ${restaurant_name}`,
    html: buildCorrectionAckHtml({ restaurant_name, city }),
    emailType: 'correction_ack',
    restaurantName: restaurant_name,
  });
}
