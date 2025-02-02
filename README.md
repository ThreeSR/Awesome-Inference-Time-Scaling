# Awesome-Inference-Time-Scaling
**Paper List of Inference/Test Time Scaling/Computing**

## 📖 Paper List (Listed in Time Order)

Scaling LLM Test-Time Compute Optimally can be More Effective than Scaling Model Parameters

Tree Search for Language Model Agents

Inference Scaling Laws: An Empirical Analysis of Compute-Optimal Inference for Problem-Solving with Language Models

CodeMonkeys: Scaling Test-Time Compute for Software Engineering

SANA 1.5: Efficient Scaling of Training-Time and Inference-Time Compute in Linear Diffusion Transformer

O1 Replication Journey -- Part 3: Inference-time Scaling for Medical Reasoning

🔹 [Inference-Time Scaling for Diffusion Models beyond Scaling Denoising Steps](https://arxiv.org/abs/2501.09732)
- 🔗 **ArXiv PDF Link:** [Paper Link](https://arxiv.org/pdf/2501.09732)
- 👤 **Authors:** Nanye Ma, Shangyuan Tong, Haolin Jia, Hexiang Hu, Yu-Chuan Su, Mingda Zhang, Xuan Yang, Yandong Li, T. Jaakkola, Xuhui Jia, Saining Xie
- 🗓️ **Date:** 2025-01-16
- 📑 **Publisher:** ArXiv
- 📝 **Abstract:** Generative models have made significant impacts across various domains, largely due to their ability to scale during training by increasing data, computational resources, and model size, a phenomenon characterized by the scaling laws. Recent research has begun to explore inference-time scaling behavior in Large Language Models (LLMs), revealing how performance can further improve with additional computation during inference. Unlike LLMs, diffusion models inherently possess the flexibility to adjust inference-time computation via the number of denoising steps, although the performance gains typically flatten after a few dozen. In this work, we explore the inference-time scaling behavior of diffusion models beyond increasing denoising steps and investigate how the generation performance can further improve with increased computation. Specifically, we consider a search problem aimed at identifying better noises for the diffusion sampling process. We structure the design space along two axes: the verifiers used to provide feedback, and the algorithms used to find better noise candidates. Through extensive experiments on class-conditioned and text-conditioned image generation benchmarks, our findings reveal that increasing inference-time compute leads to substantial improvements in the quality of samples generated by diffusion models, and with the complicated nature of images, combinations of the components in the framework can be specifically chosen to conform with different application scenario.
