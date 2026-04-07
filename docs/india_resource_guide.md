# India Resource Guide for Bio Sentinel

This document organizes high-value resources for India adaptation and implementation.

## 1. Government Surveillance Platforms

- IDSP Portal: https://idsp.mohfw.gov.in/
- IDSP Outbreak Reports: https://idsp.mohfw.gov.in/index4.php?lang=1&level=0&linkid=403&lid=3685
- IDSP Overview (NHM): https://nhm.gov.in/index4.php?lang=1&level=0&linkid=282&lid=349
- IHIP Login: https://ihip.mohfw.gov.in/idsp/#!/login
- IHIP Learning: https://ihiplearning.in/idsp/
- WHO IHIP launch note: https://www.who.int/india/news-room/detail/14-04-2021-next-gen-digital-platform-launched-pan-india-to-accelerate-outbreak-response

## 2. Digital Health Interoperability

- ABDM overview: https://www.digitalindia.gov.in/initiative/ayushman-bharat-digital-mission/
- ABDM sandbox: https://sandboxcms.abdm.gov.in/
- Health data policy: https://www.india.gov.in/my-government/documents/details/health-data-management-policy-of-ayushman-bharat-digital-mission-abdm
- ABDM docs mirror: https://docs.ohc.network/docs/care/ABDM/

## 3. CHW and Field Workflow References

- ANMOL manual: https://nhmmizoram.org/upload/Anmol%205.0.12%20User%20Manual_28May2024.pdf
- ANMOL app listing: https://play.google.com/store/apps/details?id=org.unicef.eanmapp&hl=en_NZ
- CHW readiness study: https://pmc.ncbi.nlm.nih.gov/articles/PMC9263958/

## 4. Indian Language and Medical NLP Data

- AI4Bharat Indic NLP catalog: https://github.com/AI4Bharat/indicnlp_catalog
- MILU benchmark: https://huggingface.co/datasets/ai4bharat/MILU
- MedMCQA-Indic: https://aikosh.indiaai.gov.in/home/datasets/details/medmcqa_indic.html
- Eka Indic healthcare benchmark: https://huggingface.co/datasets/ekacare/Eka-IndicMTEB

## 5. Audio and Cough Screening Resources

- CODA TB dataset publication: https://digitalcommons.montclair.edu/cgi/viewcontent.cgi?article=1072&context=computing-facpubs
- TB cough dataset details: https://pmc.ncbi.nlm.nih.gov/articles/PMC10996751/
- Real-world TB cough prediction: https://arxiv.org/abs/2307.04842

## 6. On-Device Inference and Mobile Deployment

- llama.cpp Android docs: https://github.com/ggerganov/llama.cpp/blob/master/docs/android.md
- Android tutorial for llama.cpp: https://github.com/JackZeng0208/llama.cpp-android-tutorial
- GGUF optimization guide: https://www.inferless.com/learn/gguf-optimisations-for-llms

## 7. Funding and Program Support

- IndiaAI mission portal: https://indiaai.gov.in/
- IndiaAI grants overview: https://trialect.com/grantsboard/s/indiaai-innovation-challenge

## Recommended MVP Sequence

1. Integrate IDSP-like syndrome mapping and district threshold config.
2. Launch Hindi plus one Dravidian language intake support.
3. Benchmark end-to-end latency on low-memory Android devices.
4. Add secure deferred synchronization with audit traces.
5. Execute pilot in 1 to 2 states before broader rollout.
