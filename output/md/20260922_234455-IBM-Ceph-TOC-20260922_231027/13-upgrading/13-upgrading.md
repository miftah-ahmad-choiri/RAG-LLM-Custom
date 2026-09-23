# Upgrading

> **Index:** `13`  
> **Source:** [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=upgrading](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=upgrading)

---

[Get hands-on experience with IBM tech Join one of the largest technical IBM community gatherings! →](https://www.ibm.com/events/techxchange)

Change version
9.9.1
9.9.0
8.1.0
8.0.0
7.1.0
7.0.0
6.1.0
5.3.0

Was this topic helpful?
Focus sentinel

Close

Rate this content
Thank you for your feedback!
Together, we can continue to improve IBM Documentation.
Return to topic
Focus sentinel
Focus sentinel

Close

### Thank you for your submission.

Submissions are limited to 1 per day per topic.

Focus sentinel
Focus sentinel

Close

### Error submitting rating

There has been an error sending your feedback to the team. Your comment was saved locally, if not in an incognito browser, and will be available when attempting to submit feedback again.

Please try again later.

Focus sentinel

## Upgrading

Last Updated
: 2026-06-25

Upgrade to an IBM Storage Ceph cluster running Red Hat Enterprise Linux on AMD64 and Intel 64 architectures.

While IBM values the use of inclusive language, terms that are outside of IBM's direct influence, for the sake of maintaining user understanding, are sometimes required. As other industry leaders join IBM in embracing the use of inclusive language, IBM will continue to update the documentation to reflect those changes.
© Copyright IBM Corporation 2026

?lit$5863035826$
?lit$5863035826$
?lit$5863035826$
?lit$5863035826$
?lit$5863035826$
Arabic / عربية
?lit$5863035826$
Bulgarian / Български
?lit$5863035826$
Catalan / Català
?lit$5863035826$
Czech / Čeština
?lit$5863035826$
Danish / Dansk
?lit$5863035826$
German / Deutsch
?lit$5863035826$
Greek / Ελληνικά
?lit$5863035826$
English
?lit$5863035826$
Spanish / Español
?lit$5863035826$
Finnish / Suomi
?lit$5863035826$
French / Français
?lit$5863035826$
Croatian / Hrvatski
?lit$5863035826$
Hungarian / Magyar
?lit$5863035826$
Italian / Italien
?lit$5863035826$
Hebrew / עברית
?lit$5863035826$
Japanese / 日本語
?lit$5863035826$
Korean / 한국어
?lit$5863035826$
Kazakh / Қазақша
?lit$5863035826$
Dutch / Nederlands
?lit$5863035826$
Norwegian / Norsk
?lit$5863035826$
Polish / polski
?lit$5863035826$
Portuguese/Brazil / Português/Brasil
?lit$5863035826$
Portuguese/Portugal / Português/Portugal
?lit$5863035826$
Romanian / Română
?lit$5863035826$
Russian / Русский
?lit$5863035826$
Slovak / Slovenčina
?lit$5863035826$
Slovenian / slovenščina
?lit$5863035826$
Serbian / srpski
?lit$5863035826$
Swedish / Svenska
?lit$5863035826$
Thai / ภาษาไทย
?lit$5863035826$
Turkish / Türkçe
?lit$5863035826$
Vietnamese / Việt
?lit$5863035826$
Chinese Simplified / 简体中文
?lit$5863035826$
Chinese Traditional / 繁體中文

?lit$5863035826$
?lit$5863035826$
Contact IBM
?lit$5863035826$
Privacy
?lit$5863035826$
Terms of use
?lit$5863035826$
Accessibility
?lit$5863035826$
?lit$5863035826$
?lit$5863035826$
?lit$5863035826$
?lit$5863035826$
Arabic / عربية
?lit$5863035826$
Bulgarian / Български
?lit$5863035826$
Catalan / Català
?lit$5863035826$
Czech / Čeština
?lit$5863035826$
Danish / Dansk
?lit$5863035826$
German / Deutsch
?lit$5863035826$
Greek / Ελληνικά
?lit$5863035826$
English
?lit$5863035826$
Spanish / Español
?lit$5863035826$
Finnish / Suomi
?lit$5863035826$
French / Français
?lit$5863035826$
Croatian / Hrvatski
?lit$5863035826$
Hungarian / Magyar
?lit$5863035826$
Italian / Italien
?lit$5863035826$
Hebrew / עברית
?lit$5863035826$
Japanese / 日本語
?lit$5863035826$
Korean / 한국어
?lit$5863035826$
Kazakh / Қазақша
?lit$5863035826$
Dutch / Nederlands
?lit$5863035826$
Norwegian / Norsk
?lit$5863035826$
Polish / polski
?lit$5863035826$
Portuguese/Brazil / Português/Brasil
?lit$5863035826$
Portuguese/Portugal / Português/Portugal
?lit$5863035826$
Romanian / Română
?lit$5863035826$
Russian / Русский
?lit$5863035826$
Slovak / Slovenčina
?lit$5863035826$
Slovenian / slovenščina
?lit$5863035826$
Serbian / srpski
?lit$5863035826$
Swedish / Svenska
?lit$5863035826$
Thai / ภาษาไทย
?lit$5863035826$
Turkish / Türkçe
?lit$5863035826$
Vietnamese / Việt
?lit$5863035826$
Chinese Simplified / 简体中文
?lit$5863035826$
Chinese Traditional / 繁體中文

---

*Source: [https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=upgrading](https://www.ibm.com/docs/en/storage-ceph/9.9.1?topic=upgrading)*