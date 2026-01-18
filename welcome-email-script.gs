function onFormSubmit(e) {
  var response = e.namedValues;
  var email = response['Email Address'] || response['Email address'];
  var name = response['First name'] || response['First Name'];

  if (email && email[0]) {
    sendWelcomeEmail(email[0], name ? name[0] : '');
  }
}

function sendWelcomeEmail(email, name) {
  var greeting = name ? 'Hey ' + name + '!' : 'Hey there!';

  var subject = 'Welcome to Detty Flight Deals!';

  var htmlBody = '<!DOCTYPE html>' +
'<html>' +
'<head>' +
'    <meta charset="utf-8">' +
'    <meta name="viewport" content="width=device-width,initial-scale=1.0">' +
'</head>' +
'<body style="margin:0;padding:0;background:#F5F5F5;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;">' +
'    <div style="max-width:600px;margin:0 auto;padding:20px;">' +
'        <div style="text-align:center;padding:24px 0;margin-bottom:24px;">' +
'            <div style="font-size:28px;font-weight:800;margin-bottom:8px;">' +
'                <span style="color:#009639;">Detty</span> <span style="color:#262626;">Flight Deals</span>' +
'            </div>' +
'        </div>' +
'        <div style="background:#FFFFFF;border-radius:12px;padding:32px;margin-bottom:24px;">' +
'            <div style="font-size:24px;font-weight:700;color:#0D0D0D;margin-bottom:16px;">' +
'                ' + greeting + ' Welcome to the family!' +
'            </div>' +
'            <div style="font-size:16px;color:#525252;line-height:1.6;">' +
'                <p>You are now on the list for cheap flights to Africa. Here is what to expect:</p>' +
'                <p><strong>Deal alerts in your inbox</strong><br>' +
'                When we find flights 25-50% below normal prices to Lagos, Accra, Dakar, Kinshasa, and 7 more cities - you will be the first to know.</p>' +
'                <p><strong>Three deal tiers</strong><br>' +
'                - <strong>WOW deals</strong> - Mistake fare territory. Book first, ask questions later.<br>' +
'                - <strong>Great deals</strong> - Solid savings, worth booking.<br>' +
'                - <strong>Good deals</strong> - Below average prices, good for flexible dates.</p>' +
'                <p><strong>How often?</strong><br>' +
'                We only email when there is a real deal - no spam, no fluff. Expect 1-4 emails per month depending on what we find.</p>' +
'                <p style="margin-top:24px;">Get ready for your next trip home.</p>' +
'            </div>' +
'        </div>' +
'        <div style="background:#FEF9C3;border:2px solid #FCD116;border-radius:12px;padding:24px;margin-bottom:24px;">' +
'            <div style="font-size:16px;font-weight:700;color:#0D0D0D;margin-bottom:8px;">' +
'                We are in beta!' +
'            </div>' +
'            <div style="font-size:14px;color:#525252;margin-bottom:16px;">' +
'                We are testing things out from now until the end of summer. Your feedback helps us build something great.' +
'            </div>' +
'            <a href="https://docs.google.com/forms/d/1jUBvPUjgBkoXMnaFldfkFjaJuVjA8aR0yAvXAfcmSzE/viewform" style="display:inline-block;background:#FCD116;color:#000;padding:12px 24px;border-radius:50px;text-decoration:none;font-weight:600;font-size:14px;">Share Feedback</a>' +
'        </div>' +
'        <div style="text-align:center;padding:24px 0;border-top:1px solid #E5E5E5;">' +
'            <div style="font-size:12px;color:#909090;">' +
'                You signed up for Detty Flight Deals.' +
'            </div>' +
'            <div style="font-size:12px;color:#909090;margin-top:8px;">' +
'                <a href="mailto:kyra.atekwana@gmail.com?subject=Unsubscribe%20from%20Detty%20Flight%20Deals&body=Please%20unsubscribe%20me." style="color:#909090;text-decoration:underline;">Unsubscribe</a>' +
'            </div>' +
'        </div>' +
'    </div>' +
'</body>' +
'</html>';

  GmailApp.sendEmail(email, subject, 'Welcome to Detty Flight Deals!', {
    htmlBody: htmlBody,
    name: 'Detty Flight Deals'
  });
}

function createTrigger() {
  var form = FormApp.openById('1ccn_yReCSNb2hDuTPSr3qZmH4PTF2udHUD_bFiwD_6k');
  ScriptApp.newTrigger('onFormSubmit')
    .forForm(form)
    .onFormSubmit()
    .create();
}

// Run this to test the email manually
function testWelcomeEmail() {
  sendWelcomeEmail('kyra.atekwana@gmail.com', 'Kyra');
}
