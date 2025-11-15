# Tiny Model, Big Logic: VibeThinker-1.5B

## Paper Information
- **Title**: Tiny Model, Big Logic: Diversity-Driven Optimization Elicits Large-Model Reasoning Ability in VibeThinker-1.5B
- **Authors**: Sen Xu, Yi Zhou, Wei Wang, Jixin Min, Zhibin Yin, Yingwei Dai, Shixi Liu, Lianyu Pang, Yirong Chen, Junlin Zhang (Sina Weibo Inc.)
- **ArXiv ID**: 2511.06221
- **URL**: https://arxiv.org/abs/2511.06221
- **GitHub**: https://github.com/WeiboAI/VibeThinker

## BibTeX Citation
```bibtex
@article{xu2025vibethinker,
  title={Tiny Model, Big Logic: Diversity-Driven Optimization Elicits Large-Model Reasoning Ability in VibeThinker-1.5B},
  author={Xu, Sen and Zhou, Yi and Wang, Wei and Min, Jixin and Yin, Zhibin and Dai, Yingwei and Liu, Shixi and Pang, Lianyu and Chen, Yirong and Zhang, Junlin},
  journal={arXiv preprint arXiv:2511.06221},
  year={2025}
}
```

## Key Information
- **Model Size**: 1.5B parameters
- **Base Model**: Fine-tuned variant of Alibaba's Qwen2.5-Math-1.5B
- **Key Innovation**: Spectrum-to-Signal Principle (SSP) post-training methodology
- **Training Cost**: ~$7,800

## Performance Highlights
- Outperforms DeepSeek-R1 (400x larger model) on mathematical benchmarks:
  - AIME24: 80.3 vs. 79.8
  - AIME25: 74.4 vs. 70.0
  - HMMT25: 50.4 vs. 41.7
- Competitive with closed-source models (Magistral Medium, Claude Opus 4)
- Performance on par with open-source GPT OSS-20B Medium

## Resources
- 🤗 Hugging Face: https://huggingface.co/WeiboAI/VibeThinker-1.5B
- Model Scope: Available for deployment
- Technical Report: Available
- Full ArXiv Paper: https://arxiv.org/html/2511.06221v1

## Status
- [x] Paper found and documented
- [x] GitHub repository found
- [ ] Paper review completed

## Notes
Recommended parameters: temperature 0.6 or 1.0, max token length 40960, top_p 0.95, top_k -1
