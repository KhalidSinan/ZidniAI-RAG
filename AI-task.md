# Technical Assessment: Document-Grounded RAG System

## 1\. Overview

Build a Retrieval-Augmented Generation (RAG) system that answers questions about a children's book in PDF format.
**The only required chapter of the book is number #6 (Data).**

**Document link:** [document link](https://repo.darmajaya.ac.id/5689/1/Help%20Your%20Kids%20with%20Computer%20Science_%20A%20Unique%20Visual%20Step-by-Step%20Guide%20to%20Computers%2C%20Coding%2C%20and%20Communication%20%28%20PDFDrive%20%29.pdf)

**LLM:** `meta-llama/llama-3.3-70b-instruct:free` via OpenRouter.

## 2\. Product Requirements

- **Document grounding:** Answers must rely exclusively on the provided PDF. If the document does not contain sufficient information, the system must clearly state that the question cannot be answered from the available content.
- **Language and tone:** Responses should reflect the book's language, tone, vocabulary, and intended audience.
- **Visual content:** Make a reasonable effort to retrieve and present relevant images from the PDF alongside answers when appropriate.

## 3\. Implementation Requirements

- **RAG pipeline:** Implement the complete workflow, from PDF ingestion and preprocessing to retrieval and answer generation.
- **PDF processing:** Design the pipeline to be clear, isolated, and reproducible across different chapters of the same book. Chapter-level processing should not require changes to the core pipeline.
- **Testing interface:** Provide a simple interface for submitting questions and inspecting generated answers and relevant retrieved content.
- **Model integration:** Use the specified OpenRouter model for answer generation.
- **Technical decisions:** Document the rationale behind significant technical choices, including relevant alternatives and trade-offs.

## 4\. AI-Assisted Development

AI coding assistants and vibe-coding agents are permitted.

Include a Markdown report describing your development workflow, including the context provided to AI agents, delegated tasks, and how generated code was reviewed and validated. Explain how you used AI as a programmer while retaining responsibility for engineering decisions.

## 5\. Non-Functional Requirements

- **Reliability:** Handle processing and retrieval failures gracefully.
- **Consistency:** Maintain factual consistency and apply grounding rules across queries.
- **Performance:** Provide reasonably responsive query execution and avoid unnecessary repeated processing.
- **Reproducibility:** Document dependencies and setup instructions sufficiently to reproduce the implementation.

## 6\. Deliverables and Submission

Submit a Git repository containing:

- The complete implementation and a runnable Jupyter notebook.
- The PDF processing and RAG pipeline, organized for independent execution and inspection.
- A simple question-answering interface.
- Setup instructions and dependency specifications.
- The AI-assisted development report and technical decision rationale.

The repository must preserve the development history through meaningful commits and branches.

**Priority:** Complete the core requirements before implementing optional enhancements. Additional improvements are welcome once the main functionality is working.

## 7\. Evaluation Criteria

Submissions will be evaluated on:

- Answer relevance and faithfulness to the PDF.
- Handling of unsupported questions.
- Retrieval and presentation of relevant images.
- Language and tone consistency.
- Pipeline design, modularity, and chapter-level reproducibility.
- Reliability, consistency, and performance.
- Technical reasoning, testing, and Git development history.
