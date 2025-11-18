# A-MEM: Agentic Memory for LLM Agents

## Metadata
- **Title**: A-MEM: Agentic Memory for LLM Agents
- **Authors**: Wujiang Xu, Zujie Liang, Kai Mei, Hang Gao, Juntao Tan, Yongfeng Zhang
- **Year**: 2025
- **Venue**: arXiv preprint arXiv:2502.12110
- **URL**: https://arxiv.org/abs/2502.12110
- **BibTeX**:
```
@article{xu2025amem,
  title={A-MEM: Agentic Memory for LLM Agents},
  author={Xu, Wujiang and Liang, Zujie and Mei, Kai and Gao, Hang and Tan, Juntao and Zhang, Yongfeng},
  journal={arXiv preprint arXiv:2502.12110},
  year={2025}
}
```

## Abstract
While large language model (LLM) agents can effectively use external tools for complex real-world tasks, they require memory systems to leverage historical experiences. Existing memory systems for LLM agents provide basic memory storage functionality. These systems require agent developers to predefine memory storage structures, specify storage points within the workflow, and establish retrieval timing. Meanwhile, to improve structured memory organization, Mem0 and Letta introduced memory graphs, but they are static and lack dynamic evolution. Our system introduces an agentic memory architecture that enables autonomous and flexible memory management for LLM agents. For each new memory, we construct comprehensive notes, which integrates multiple representations: structured textual attributes and embedding vectors for semantic search. We use LLM agents to manage the memory lifecycle: linking new memories to existing ones, updating memories, and pruning irrelevant ones. Our approach draws inspiration from human memory and knowledge graph evolution, enhancing LLM agents’ long-term memory capabilities and adaptability.

## GitHub Repository
Official repository: https://github.com/agiresearch/A-mem

## Notes

