Subject: BharatTrip Take-Home Task Submission - [Your Name]

Hi [Recruiter's Name],

Please find attached my submission for the AI Operations Associate take-home task. 

Attached you will find:
1. **write_up.pdf**: My analysis of the data, the core problem definition (100 dropped tickets and 149 mismatches), and the proposed operational solution.

You can access my working AI prototype here:
* **Live Web App**: [https://vktoflyss.streamlit.app/](https://vktoflyss.streamlit.app/)
* **GitHub Repository**: [https://github.com/vktofly/SSOT.git](https://github.com/vktofly/SSOT.git)

### How to Run and Test the Prototype
To test the live application directly in your browser, please use the following mock credentials. The application sits behind an Identity Gateway to demonstrate enterprise-grade Role-Based Access Control (RBAC) and Data Masking:
* **Manager Role** (Full Access & Unmasked Data): 
  * Username: `manager` 
  * Password: `admin123`
* **Operator Role** (Restricted Access & Masked PII): 
  * Username: `operator` 
  * Password: `agent123`

### Beyond the Brief: Why I Built What I Built
The brief asked for a prototype that solves a meaningful slice of the problem. While I successfully implemented the core LLM ingestion and reconciliation logic, I wanted to demonstrate that I understand the difference between a simple AI script and a **deployable enterprise tool**. 

To that end, I went beyond the basic requirements and engineered several robust features:
1. **Data Privacy (PII Redaction):** In the real world, WhatsApp logs contain sensitive customer data. I implemented an automatic redaction layer (hiding emails, phones, and credit cards) before data hits the DB, and dynamic UI masking for lower-level operators.
2. **AI Confidence Guardrails:** LLMs can hallucinate. The ingestion agent scores its own extractions and flags low-confidence data for mandatory human review in the UI.
3. **Data Loss Prevention (DLP):** I implemented UI-level CSS locks to prevent text selection and copying of sensitive fields.
4. **Auditability:** Every Human-in-the-Loop (HITL) approval is logged and can be exported as a secure CSV to ensure financial compliance.
5. **Database Explorer:** A unified global search tab that acts as the ultimate Single Source of Truth, breaking down the silos between the Support and Finance teams.

I treated this prototype as if it were a real product heading into a production environment where security, accountability, and operational workflows are just as important as the AI itself.

Thank you for your time, and I look forward to discussing the architecture and my findings with the team.

Best regards,

[Your Name]
[Your Phone Number]
[Your LinkedIn Profile]
