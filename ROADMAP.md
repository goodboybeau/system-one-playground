# Roadmap

Ideas, roughly in order. Issues and PRs welcome.

- **Fine-tune in the playground.** Train Laya or Kev on your own labelled JSONL, fit temperatures, and compare before and after side by side.
- **Bigger models via MLX 4-bit**, such as Kev 9B or a 27B chat-layout model. The independent Decision Index puts the 27B class level with Jev.
- **More engines:** Bespoke Nimble, Intern-Decision, Hopper, GLiNER2 Decide, Winnow (llama.cpp).
- **Batch throughput:** several states per forward pass. Most engines support it internally; the playground only measures single requests today.
- **Shared leaderboards:** import other people's exported results and compare chips.
- **Linux and CUDA:** the design is portable (engines are just processes), but sandboxing and memory accounting are macOS-specific today.
