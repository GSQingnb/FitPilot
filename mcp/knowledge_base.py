"""
RAG 知识库 —— 基于 ChromaDB 的真实检索实现（FitPilot 健身领域）。

功能：
  1. 文档导入：将文本切片后存入 ChromaDB（自动生成 Embedding）
  2. 语义检索：根据 query 从知识库中检索最相关的文档片段
  3. 与 MCP 工具框架集成：作为 knowledge_search 工具的真实 handler

ChromaDB 在这里的角色：
  - memory/ 中用于存储对话记忆（情景记忆 + 用户画像）
  - 这里用于存储知识库文档（RAG 检索）
  两者是不同的 collection，互不干扰。
"""
import hashlib
import logging
from typing import Any, Dict, List, Optional

import chromadb

logger = logging.getLogger(__name__)


class KnowledgeBase:
    """
    基于 ChromaDB 的 RAG 知识库。

    ChromaDB 内置了 Embedding 模型（all-MiniLM-L6-v2），
    调用 add() 时自动生成向量，query() 时自动做语义匹配。
    不需要额外调用 Anthropic Embeddings API。
    """

    COLLECTION_NAME = "knowledge_base"

    def __init__(
        self,
        chroma_host: str = "localhost",
        chroma_port: int = 8000,
        chroma_path: str = "./data/chroma",
    ):
        # 优先连接独立 ChromaDB 服务（服务端内置 embedding 模型，客户端无需下载）
        self._use_server = False
        try:
            self._client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
            self._client.heartbeat()
            self._use_server = True
            logger.info(f"知识库 ChromaDB 已连接: {chroma_host}:{chroma_port}")
        except Exception:
            logger.info(f"知识库 ChromaDB 服务不可用，使用本地模式: {chroma_path}")
            self._client = chromadb.PersistentClient(
                path=chroma_path,
                settings=chromadb.Settings(anonymized_telemetry=False),
            )

        # 使用服务端时不传 embedding_function，让服务端处理
        # 本地模式时也不传，使用 ChromaDB 默认的（会触发模型下载）
        self._collection = self._client.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"description": "FitPilot RAG 健身知识库"},
        )

        # 如果知识库为空，导入默认文档
        if self._collection.count() == 0:
            self._load_default_docs()

    # ── 文档管理 ──────────────────────────────────────────────────────────────

    def add_documents(self, documents: List[Dict[str, str]]) -> int:
        """
        批量导入文档到知识库。

        documents 格式: [{"title": "...", "content": "..."}, ...]
        长文档会自动切片（每片 500 字）。
        """
        ids, docs, metas = [], [], []

        for doc in documents:
            title   = doc.get("title", "")
            content = doc.get("content", "")
            chunks  = self._chunk_text(content, chunk_size=500)

            for i, chunk in enumerate(chunks):
                doc_id = hashlib.md5(f"{title}_{i}_{chunk[:50]}".encode()).hexdigest()
                ids.append(doc_id)
                docs.append(chunk)
                metas.append({"title": title, "chunk_index": i, "total_chunks": len(chunks)})

        if ids:
            # ChromaDB 会自动生成 Embedding
            self._collection.add(ids=ids, documents=docs, metadatas=metas)
            logger.info(f"知识库导入 {len(ids)} 个文档片段")

        return len(ids)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        语义检索：根据 query 返回最相关的文档片段。

        ChromaDB 内部自动将 query 转为向量，与存储的文档向量做余弦相似度匹配。
        """
        results = self._collection.query(
            query_texts=[query],
            n_results=top_k,
        )

        items = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            ):
                items.append({
                    "title":    meta.get("title", ""),
                    "content":  doc,
                    "score":    round(1.0 - dist, 4),  # ChromaDB 返回距离，转为相似度
                    "chunk":    meta.get("chunk_index", 0),
                })

        return items

    @property
    def doc_count(self) -> int:
        return self._collection.count()

    # ── MCP 工具 handler ─────────────────────────────────────────────────────

    async def search_handler(self, params: Dict[str, Any], context: Any) -> List[Dict]:
        """
        作为 MCP 工具的 handler 注册。

        MCPToolManager.register(Tool(
            name="knowledge_search",
            handler=kb.search_handler,
            ...
        ))
        """
        query = params.get("query", "")
        top_k = params.get("top_k", 5)
        return self.search(query, top_k=top_k)

    # ── 内部方法 ──────────────────────────────────────────────────────────────

    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """将长文本按 chunk_size 切片，保留语义完整性（按句号/换行切分）。"""
        if len(text) <= chunk_size:
            return [text] if text.strip() else []

        chunks = []
        current = ""
        # 按句子切分
        sentences = text.replace("\n", "。").split("。")
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            if len(current) + len(sent) + 1 > chunk_size:
                if current:
                    chunks.append(current)
                current = sent
            else:
                current = f"{current}。{sent}" if current else sent

        if current:
            chunks.append(current)

        return chunks

    def _load_default_docs(self) -> None:
        """导入默认知识库文档（健身基础知识）。"""
        default_docs = [
            {
                "title": "渐进超负荷原则",
                "content": (
                    "渐进超负荷（Progressive Overload）是力量训练的核心原则。"
                    "指在训练过程中逐步增加对肌肉的压力刺激，迫使身体不断适应和变强。"
                    "实现渐进超负荷的方法：1. 增加重量（最常见）；2. 增加次数（同样的重量做更多次）；"
                    "3. 增加组数；4. 缩短组间休息时间；5. 增加训练频率；6. 增加动作幅度。"
                    "建议每次只增加 2.5-5kg（上肢）或 5-10kg（下肢），或每周增加 1-2 次重复。"
                    "过于激进的增重会增加受伤风险。如果没有实现渐进超负荷，肌肉就没有持续增长的理由。"
                ),
            },
            {
                "title": "RPE 基础说明",
                "content": (
                    "RPE（Rating of Perceived Exertion，自感用力程度）是衡量训练强度的主观指标。"
                    "常用 1-10 分制：RPE 6 = 轻松，可做 4-6 个以上；RPE 7 = 中等偏重，可做 3-4 个以上；"
                    "RPE 8 = 重，可做 2 个以上；RPE 9 = 很重，可做 1 个以上；RPE 10 = 力竭，无法再做一个。"
                    "一般增肌训练建议每组在 RPE 7-9 之间，即保留 1-3 个的余力。"
                    "RPE 10（完全力竭）不应在每一组都使用，否则恢复压力过大。"
                    "持续 RPE 9-10 可能表示训练量过高或恢复不足。"
                    "RPE 也可用于衡量整个训练课的疲劳程度（sRPE = RPE × 训练时长分钟数）。"
                ),
            },
            {
                "title": "增肌训练基础原则",
                "content": (
                    "增肌（肌肥大）训练的基本原则。"
                    "1. 训练量：每个肌群每周 10-20 组是大多数人的有效范围。"
                    "2. 强度：每组 6-12 次重复（使用 65-85% 1RM）对增肌效果最佳，但 5-30 次范围内都能有效增肌。"
                    "3. 频率：同一肌群每周训练 2 次通常优于 1 次。"
                    "4. 渐进超负荷：长期来看必须增加训练刺激。"
                    "5. 营养支持：充足的蛋白质摄入（每公斤体重 1.6-2.2g/d）和适当热量盈余。"
                    "6. 睡眠与恢复：每晚 7-9 小时睡眠，肌肉在休息时生长。"
                    "初学者不需要追求极致训练量，先建立动作质量和训练习惯。"
                ),
            },
            {
                "title": "常见训练拆分",
                "content": (
                    "训练拆分（Training Split）指如何在一周内分配不同肌群的训练。"
                    "全身训练（Full Body）：每次训练覆盖全身主要肌群，适合新手和每周 2-3 天训练。"
                    "上下肢拆分（Upper/Lower）：一天上肢一天下肢交替，适合每周 4 天，兼顾频率和恢复。"
                    "推拉腿拆分（PPL，Push/Pull/Legs）：推类动作（胸肩三头）、拉类动作（背二头）、腿部，"
                    "每周可练 3 天或 6 天（练 3 休 1）。"
                    "五分化（Bro Split）：胸、背、肩、腿、手臂各一天，每周 5 天，自然训练者不如高频拆分效果好。"
                    "选择哪种拆分取决于：训练频率、恢复能力、个人偏好和经验水平。"
                    "初学者建议从全身训练或上下肢拆分开始。"
                ),
            },
            {
                "title": "杠铃卧推动作说明",
                "content": (
                    "杠铃卧推（Barbell Bench Press）是发展胸肌、肩前束和肱三头肌的经典复合动作。"
                    "动作要点：1. 躺在平板凳上，眼睛位于杠铃正下方；2. 握距比肩略宽（约 1.5 倍肩宽）；"
                    "3. 肩胛骨收紧下沉，胸椎微微挺起（起桥）；4. 脚踩稳地面；"
                    "5. 下放时杠铃触及下胸位置（乳头线），肘部与躯干呈 45-75 度角；"
                    "6. 推起时杠铃轨迹略向头部方向移动，锁定时不要过度伸展肘部。"
                    "常见错误：握距过宽增加肩关节压力、肘部打开过大（90度）、臀部离开凳面、"
                    "半程卧推（不触胸）。无杠铃时可替代动作：哑铃卧推、俯卧撑（负重）、器械推胸。"
                ),
            },
            {
                "title": "深蹲动作说明",
                "content": (
                    "杠铃深蹲（Barbell Back Squat）被称为动作之王，主要训练股四头肌、臀大肌、腘绳肌和核心。"
                    "动作要点：1. 杠铃置于斜方肌上方（高杠）或后三角肌上（低杠）；"
                    "2. 站距略宽于肩，脚尖微微外八（约 15-30 度）；"
                    "3. 下蹲时膝盖沿脚尖方向移动，髋部向后向下坐；"
                    "4. 下蹲到大腿与地面平行或略低（取决于髋关节活动度）；"
                    "5. 保持脊柱中立，核心收紧，不要弓背或过度前倾；"
                    "6. 驱动时脚掌全掌发力，膝盖不要内扣。"
                    "常见错误：脚跟离地、膝盖内扣、上半身前倾过多（屁股眨眼）、深度不足。"
                    "替代动作：高脚杯深蹲（新手友好）、保加利亚分腿蹲、腿举、前蹲。"
                ),
            },
            {
                "title": "硬拉动作说明",
                "content": (
                    "硬拉（Deadlift）是训练后链肌群（竖脊肌、臀大肌、腘绳肌、斜方肌）的核心动作。"
                    "传统硬拉动作要点：1. 站距与髋同宽，杠铃位于脚掌中段上方；"
                    "2. 握距在膝盖外侧（不碰腿），正反握或双正握+助力带；"
                    "3. 下放时髋部向后推，小腿尽量保持垂直，杠铃贴近小腿下滑；"
                    "4. 拉起时保持脊柱中立，核心收紧，先伸膝再伸髋，杠铃贴近身体；"
                    "5. 锁定位置时臀部收紧，不要过度后仰。"
                    "常见错误：圆背（最危险）、杠铃远离身体、启动时臀位过高（变成直腿硬拉）、"
                    "锁定过度后仰。替代动作：六角杠硬拉（对腰椎更友好）、罗马尼亚硬拉、壶铃摇摆。"
                    "已有椎间盘问题的人群应在医生或物理治疗师评估后再决定是否进行硬拉训练。"
                ),
            },
            {
                "title": "常见器械替代关系",
                "content": (
                    "器械替代指南：当缺少特定器械时，可参考以下替代方案。"
                    "杠铃卧推 → 哑铃卧推（更大活动范围，对肩关节更友好）、俯卧撑（负重背包增加强度）、器械推胸。"
                    "杠铃深蹲 → 高脚杯深蹲（哑铃/壶铃，新手入门首选）、保加利亚分腿蹲（单腿，减少脊柱负荷）、腿举机。"
                    "杠铃硬拉 → 六角杠硬拉（减少腰椎剪切力）、壶铃摇摆（爆发力+后链）、单腿罗马尼亚硬拉（腘绳肌+平衡）。"
                    "杠铃划船 → 哑铃单臂划船（更好的背阔肌感受）、坐姿绳索划船、TRX 反向划船。"
                    "引体向上 → 弹力带辅助引体、高位下拉、反向划船（降低难度）。"
                    "通用替代原则：同目标肌群、同动作模式（推/拉/蹲/铰链）、可渐进加载、适合个人关节条件。"
                ),
            },
            {
                "title": "训练恢复与休息",
                "content": (
                    "训练恢复是进步的关键，肌肉在休息时生长而非训练时。"
                    "组间休息：力量训练（1-5 次）建议 3-5 分钟，增肌训练（6-12 次）建议 1.5-3 分钟，"
                    "耐力训练（15+ 次）建议 30-90 秒。"
                    "训练日间休息：同一肌群至少间隔 48 小时再训练。"
                    "恢复不足的信号：持续酸痛超过 72 小时、训练表现下降、静息心率升高、"
                    "睡眠质量下降、对训练缺乏兴趣。"
                    "积极恢复方法：轻度有氧（散步/骑行）、拉伸、泡沫轴、充足睡眠和营养。"
                    "减载周（Deload）：每 4-8 周安排一周训练量降至正常的 50-60%，帮助身体充分恢复。"
                    "如果长期感觉恢复不过来，应减少训练量或频率，而非强行坚持。"
                ),
            },
            {
                "title": "健身安全边界",
                "content": (
                    "健身训练安全须知。"
                    "以下情况应停止当前训练并咨询医生或物理治疗师：关节刺痛（区别于肌肉酸痛）、"
                    "训练中突发剧烈疼痛、关节弹响伴随疼痛、单侧力量突然显著下降、"
                    "头晕/眩晕/视力模糊、胸痛/胸闷/呼吸困难、训练后关节持续肿胀。"
                    "以下情况需要专业评估：已知椎间盘突出、关节手术史、心血管疾病、"
                    "高血压未控制、怀孕、骨质疏松。"
                    "一般安全原则：每次训练前进行 5-10 分钟热身（动态拉伸+轻重量激活）；"
                    "学习新动作时先用轻重量练习动作模式；使用保护杠或保护者处理大重量；"
                    "循序渐进，不要为了追求重量牺牲动作质量。"
                    "FitPilot 提供的所有信息仅用于一般健身教育目的，不构成医疗建议。"
                    "如有任何健康疑虑，请咨询合格的医疗专业人员。"
                ),
            },
        ]
        self.add_documents(default_docs)
        logger.info(f"已导入默认健身知识库: {len(default_docs)} 篇文档")
