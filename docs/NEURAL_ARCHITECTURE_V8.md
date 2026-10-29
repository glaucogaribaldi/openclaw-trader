# 🧠 TRE OS v8.7 — Neural & Microstructure Architecture Map (`NeoQuasar/Kronos-mini` + Online RLS + Kalman)

**Document ID:** `TRE-OS-V8.7-NEURAL-ARCH-2026-10-25`  
**Interactive Live Visualizer:** Available natively on `http://34.28.19.242:8080` (**Tab `02. Neural Brain & Kronos`**)  
**Foundation Model Reference:** Shi et al., *"Kronos: A Foundation Model for the Language of Financial Markets"*, Tsinghua University (`arXiv:2508.02739v1`)

---

## 1. End-to-End Hybrid Neural & Microstructure Topology (Mermaid)

```mermaid
flowchart LR
    subgraph L1["01. SENSORY INPUT TENSORS (15s / 30s)"]
        K5["5m K-Lines\n(300 bars × 6)"]
        K15["15m K-Lines\n(160 bars × 6)"]
        K1H["1H K-Lines\n(80 bars × 6)"]
        L2["OKX L2 Book (5 lvls)\nOBI · Stoikov µPx · Cont OFI"]
        TAPE["Trade Tape (25 fills)\nVPIN Toxicity · Hawkes λ"]
        PERP["OKX Perp Swap Radar\n524 USDT-SWAP Basis (bps)"]
    end

    subgraph L2_BSQ["02. BSQ HYPERPLANE TOKENIZER (2²⁰)"]
        NORM["Instance Z-Score Norm\nClip [-5.0, +5.0]"]
        BSQ["BinarySphericalQuantizer\ns1_bits=10 (1024) × s2_bits=10 (1024)\n.eval() Deterministic Mode"]
    end

    subgraph L3_KRONOS["03. KRONOS-MINI (4.1M) TRANSFORMER"]
        EMB["Hierarchical Embedding\n+ Time Stamp Encoding (min, hour, dow)"]
        TR["4× Transformer Blocks\nd_model=256 · RoPE · SwiGLU"]
        HEAD["DualHead + DependencyAwareLayer\nAutoregressive s1 ➔ s2 Rollout\n(T=0.60, top_p=0.90, N=3)"]
        TENSOR["Pre-Mean Tensor (3, 12, 6)\n• Eq.13 Path-Mean Return (1h/2h/12h)\n• Eq.12 Realized Volatility\n• tp_touch_prob_1h (≥+26 bps)\n• kronos_zscore_1h & vol_surge\n• 3-Horizon Alignment (1h+2h+12h)"]
    end

    subgraph L4_RLS["04. STREAMING RLS + KALMAN"]
        KAL["2-State Kalman Filter\n[Price, Velocity bps/s]"]
        RLS["Online RLS (d=6, λ=0.985)\n• P_t Covariance Persistence\n• Intercept w[0] ∈ [-2.5, +2.5]\n• Positivity w[OBI,OFI,α] ≥ +0.5"]
    end

    subgraph L5_EXEC["05. ENSEMBLE FUSION & MAKER EXECUTION"]
        FUSE["Predictive Blend\n45% RLS/Kalman + 35% Kronos 3H\n+ 12% LLM Council + 8% BTC Lag"]
        OPP["Multi-Factor OppScore\n+Rebound +TPProb +ZScore\n+PerpSqueeze -VPIN -InvWeight"]
        MAKER["100% Post-Only Maker (OKX EEA)\n• _ceil_px() Floor ≥ +24/+25 bps\n• clOrdId Idempotency\n• Cannibal Ratchet ($5.20)\n• Dec 31 Cashout Engine (Stage 1-4)"]
    end

    K5 & K15 & K1H --> NORM --> BSQ --> EMB --> TR --> HEAD --> TENSOR
    L2 & TAPE --> KAL --> RLS
    TENSOR --> FUSE
    RLS --> FUSE
    PERP --> OPP
    FUSE --> OPP --> MAKER
```

---

## 2. PyTorch Layer-by-Layer Architecture of `NeoQuasar/Kronos-mini (4.1M)`

Inspected directly from `/home/zavattoni_giacomo/Kronos/model/kronos.py` and `/home/zavattoni_giacomo/Kronos/model/module.py`:

| Stage | Module Name | Input Shape | Output Shape | Key Parameters & Mathematical Role |
| :---: | :--- | :---: | :---: | :--- |
| **01** | `InstanceNorm + Clip` | `(B, T, 6)` | `(B, T, 6)` | Per-window mean/std normalization of `[open, high, low, close, volume, amount]`, clipped to `[-5.0, +5.0]`. |
| **02** | `KronosTokenizer.embed` + `enc_layers` (`3× TransformerBlock`) | `(B, T, 6)` | `(B, T, 256)` | Projects 6D K-line features into `d_model = 256` latent representation. |
| **03** | `BSQuantizer` (`BinarySphericalQuantizer`) | `(B, T, 256)` | `s1: (B, T)`, `s2: (B, T)` | Projects latent vectors onto the `20D` unit hypersphere (`s1_bits=10` coarse sub-token `[0..1023]`, `s2_bits=10` fine residual sub-token `[0..1023]`). |
| **04** | `HierarchicalEmbedding` + `TemporalEmbedding` | `s1, s2: (B*N, T)` | `(B*N, T, 256)` | Combines `s1/s2` token embeddings with calendar embeddings (`minute`, `hour`, `weekday`, `day`, `month`). |
| **05** | `Kronos.transformer` (`4× TransformerBlock`) | `(B*N, T, 256)` | `(B*N, T, 256)` | Causal self-attention with **Rotary Position Embeddings (`RoPE`)**, `RMSNorm`, and `SwiGLU` feed-forward networks. |
| **06** | `DualHead.head_s1` ➔ `DependencyAwareLayer` ➔ `DualHead.head_s2` | `(B*N, T, 256)` | `logits_s1 (1024)`, `logits_s2 (1024)` | First samples coarse sub-token `s1` (`T=0.60, top_p=0.90`), conditions on `s1` via cross-attention, then samples fine sub-token `s2`. |
| **07** | `_predict_paths_pre_mean` (`KronosTokenizer.decode`) | `s1, s2` rollouts | **`raw_paths: (N=3, H=12, 6)`** | Decodes all `N=3` trajectories **before** `np.mean(axis=0)` to preserve full path distribution (`tp_touch_prob_1h`, `pred_volatility_1h_bps`, `kronos_zscore_1h`). |
