# Multi-level Testing Protocol

This document outlines the mandatory testing phases for all web developments within the SLCM project. Adherence to these protocols ensures technical reliability, security, and a high-quality user experience.

## 1. Technical Check
- **Code Integrity:** Ensure all HTML, CSS, and JavaScript are syntactically correct and follow project standards.
- **Functionality:** Verify that all interactive elements (buttons, forms, links, navigation) function as intended.
- **Performance:** Check page load times and ensure assets are optimized.
- **Cross-browser Compatibility:** Test the application in latest versions of Chrome, Firefox, Safari, and Edge.

## 2. Security Check
- **Data Protection:** Ensure no sensitive information (API keys, credentials, PII) is exposed in the source code or client-side storage.
- **Form Security:** Validate that all user inputs are sanitized and protected against common vulnerabilities like XSS and SQL Injection.
- **Access Control:** Verify that only authorized users can access protected routes and data.

## 3. UI (Usability) Check
- **Responsive Design:** Verify that the layout adapts correctly to different screen sizes (Mobile, Tablet, Desktop).
- **Accessibility:** Ensure the interface is navigable via keyboard and compatible with screen readers (ARIA labels, alt text for images).
- **User Flow:** Confirm that the user journey is logical, intuitive, and consistent.

## 4. Language and Spell Check
- **English Standard:** Strictly use **English (UK)** and **English (India)** (e.g., *programme*, *colour*, *optimise*).
- **Casing Rules:**
    - **Sentence case:** Use for form fields, subtitles, and questions.
    - **Title Case:** Use for main headings, course titles, and primary action buttons.
    - **No UPPER case:** Avoid all-caps text as it is distracting.
- **Voice and Tone:** Use active voice and maintain a friendly, professional tenor.
- **Brevity:** Keep instructions short and avoid continuous tense in forms.
- **Spelling:** Perform a comprehensive spell check before any release.

## 5. Final Verification
- A change is considered complete only after it has passed all the above checks and has been empirically verified.
