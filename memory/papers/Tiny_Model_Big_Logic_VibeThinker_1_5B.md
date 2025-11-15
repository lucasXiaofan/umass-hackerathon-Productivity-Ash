# Tiny Model, Big Logic: Diversity-Driven Optimization Elicits Large-Model Reasoning Ability in VibeThinker-1.5B

## Paper Info
- **Title**: Tiny Model, Big Logic: Diversity-Driven Optimization Elicits Large-Model Reasoning Ability in VibeThinker-1.5B
- **Submission Date**: Nov 9, 2025
- **arXiv ID**: 2511.06221
- **arXiv URL**: https://arxiv.org/abs/2511.06221
- **HTML Version**: https://arxiv.org/html/2511.06221v1

## BibTeX Citation
```bibtex
@misc{xu2025tinymodelbiglogic,
  title={Tiny Model, Big Logic: Diversity-Driven Optimization Elicits Large-Model Reasoning Ability in VibeThinker-1.5B},
  author={Sen Xu and Yi Zhou and Wei Wang and Jixin Min and Zhibin Yin and Yingwei Dai and Shixi Liu and Lianyu Pang and Yirong Chen and Junlin Zhang},
  year={2025},
  eprint={2511.06221},
  archivePrefix={arXiv},
  primaryClass={cs.LG}
}
```

## GitHub Repository
- **URL**: https://github.com/WeiboAI/VibeThinker
- **Status**: Open-source ✓
- **Model on HuggingFace**: https://huggingface.co/WeiboAI/VibeThinker-1.5B

## Paper Summary
This paper introduces VibeThinker-1.5B, a 1.5B-parameter dense model that challenges the prevailing notion that small models lack robust reasoning capabilities. The key innovation is the **Spectrum-to-Signal Principle (SSP)** training methodology:

- **Two-Stage Diversity-Exploring Distillation (SFT)**: Generates broad spectrum of solutions
- **MaxEnt-Guided Policy Optimization (RL)**: Amplifies correct signals
- **Training Cost**: Only $7,800 total training cost

## Key Results
- **Outperforms DeepSeek R1 (671B)** on 3 math benchmarks:
  - AIME24: 80.3 vs 79.8 (400x smaller!)
  - AIME25: 74.4 vs 70.0
  - HMMT25: 50.4 vs 41.7

- **Comparable to Large Models**:
  - On par with GPT OSS-20B Medium, Magistral Medium, Claude Opus 4
  
- **LiveCodeBench V6**: Score 51.1 (vs Magistral Medium's 50.3)

## Review Status
⏳ Waiting for user review...

## Personal Notes
(To be filled after review)
