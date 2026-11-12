# WhatsApp templates to create in Meta WhatsApp Manager

Language `en_US` (change `WHATSAPP_TEMPLATE_LANG` if different). Template names are settings in `.env`
(`WA_TPL_*`); the defaults are shown. Variables must be filled in this exact order.
Webhook URL for delivery status: `https://<your-api>/webhooks/whatsapp`, verify token = `WHATSAPP_VERIFY_TOKEN`
(subscribe to the "messages" field).

| Setting | Default name | Header | Body variables |
|---|---|---|---|
| WA_TPL_WELCOME | customer_welcome | none | {{1}} customer, {{2}} PBA name, {{3}} showroom |
| WA_TPL_RECEIPT | booking_receipt | Document (PDF) | {{1}} customer, {{2}} receipt no, {{3}} amount paid (Rs), {{4}} I AGREE link |
| WA_TPL_INSURANCE | insurance_policy | Document (PDF) | {{1}} customer, {{2}} vehicle, {{3}} policy no |
| WA_TPL_DELIVERY | delivery_receipt | Document (PDF) | {{1}} customer, {{2}} vehicle, {{3}} delivery receipt no, {{4}} I AGREE link |
| WA_TPL_ENGAGEMENT | delivery_engagement | none | {{1}} customer, {{2}} model, {{3}} dealership, {{4}} KTM India app link, {{5}} Instagram link, {{6}} Google review link |
| WA_TPL_REVIEW | google_review_request | none | old: {{1}} Google review link. New (set WA_REVIEW_PARAMS=4): {{1}} showroom, {{2}} Google review link, {{3}} KTM India app link, {{4}} Instagram link |
| WA_TPL_TEST_RIDE | test_ride_scheduled | none | {{1}} recipient name, {{2}} customer, {{3}} model, {{4}} date, {{5}} time/slot, {{6}} location, {{7}} contact person (CRE/PBA) |

Suggested wording:

**customer_welcome** - Dear {{1}}, thank you for your interest in KTM at {{3}}. {{2}} will be your sales advisor and will contact you shortly.

**booking_receipt** - Dear {{1}}, thank you for your booking. Your receipt {{2}} for Rs. {{3}} is attached. Please confirm it here: {{4}}

**insurance_policy** - Dear {{1}}, your insurance policy {{3}} for your {{2}} is attached.

**delivery_receipt** - Dear {{1}}, congratulations on your {{2}}! Your delivery receipt {{3}} is attached. Please acknowledge it here: {{4}}

**delivery_engagement** - Dear {{1}}, congratulations on your new KTM {{2}}! Thank you for choosing {{3}}.
KTM India App - register your vehicle and book your first service: {{4}}
Follow us on Instagram and share your delivery moments: {{5}}
Please share your experience on Google: {{6}}
Thank you for being a part of the KTM family! Regards, {{3}}

**google_review_request** (old, 1 variable) - Dear Customer, thank you for choosing us! We value your feedback. Please share your experience on Google: {{1}}. Your feedback helps us improve.

**google_review_request_v2** (new, 4 variables; set WA_TPL_REVIEW=google_review_request_v2 and WA_REVIEW_PARAMS=4 after Meta approves it) -
THANK YOU FOR VISITING S.K. AUTOMOBILES, {{1}}! Dear Customer, thank you for visiting our showroom! We truly appreciate your trust in us.
We'd love your feedback - please leave us a quick Google Review: {{2}}
KTM India App - book your service appointment: {{3}}
Follow us on Instagram for delivery highlights and the latest KTM updates: {{4}}
Interested in a test ride? Contact us to schedule one. Thank you for choosing us. RIDE ORANGE! - Team S.K. Automobiles

**test_ride_scheduled** - Hello {{1}}, a test ride is scheduled for {{2}} on the {{3}} - date {{4}}, time {{5}}, at {{6}}. Contact: {{7}}.
