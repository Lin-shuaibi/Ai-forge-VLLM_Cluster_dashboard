"""AI Chat service for Dashboard control."""
import json
import httpx
from typing import Optional, Dict, List, AsyncGenerator
from dataclasses import dataclass, field

from services.log_manager import log_manager


@dataclass
class AIConfig:
    api_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model_name: str = "gpt-4o"
    use_local_vllm: bool = False
    local_vllm_url: str = "http://localhost:8000/v1"
    local_model_name: str = "llm"


class AIChatService:
    """AI Chat service that can control the platform via function calling."""

    def __init__(self):
        self.config = AIConfig()
        self.conversations: Dict[str, List[dict]] = {}

    def get_config(self) -> dict:
        return {
            "api_url": self.config.api_url,
            "api_key": "***" + self.config.api_key[-4:] if len(self.config.api_key) > 4 else "",
            "model_name": self.config.model_name,
            "use_local_vllm": self.config.use_local_vllm,
            "local_vllm_url": self.config.local_vllm_url,
            "local_model_name": self.config.local_model_name,
        }

    def update_config(self, **kwargs):
        for k, v in kwargs.items():
            if hasattr(self.config, k) and v is not None:
                setattr(self.config, k, v)

    def _get_effective_config(self):
        if self.config.use_local_vllm:
            return self.config.local_vllm_url, self.config.local_model_name, ""
        return self.config.api_url, self.config.model_name, self.config.api_key

    def _get_tools(self) -> list:
        return [
            {
                "type": "function",
                "function": {
                    "name": "create_cluster",
                    "description": "创建一个新的Ray集群",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string", "description": "集群名称"},
                            "head_nodes": {"type": "integer", "description": "头节点数量"},
                            "worker_nodes": {"type": "integer", "description": "工作节点数量"},
                            "gpu_per_node": {"type": "integer", "description": "每节点GPU数量"},
                        },
                        "required": ["name"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "start_model",
                    "description": "在指定集群上启动vLLM模型服务",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "cluster_id": {"type": "string", "description": "集群ID"},
                            "model_path": {"type": "string", "description": "模型路径"},
                            "model_name": {"type": "string", "description": "模型显示名称"},
                            "tensor_parallel_size": {"type": "integer", "description": "张量并行度"},
                        },
                        "required": ["cluster_id", "model_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "run_benchmark",
                    "description": "运行性能测试",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "model_path": {"type": "string", "description": "模型路径"},
                            "input_len": {"type": "integer", "description": "输入token长度"},
                            "output_len": {"type": "integer", "description": "输出token长度"},
                            "num_prompts": {"type": "integer", "description": "请求数量"},
                        },
                        "required": ["model_path"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_clusters",
                    "description": "列出所有集群",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_models",
                    "description": "列出所有模型服务",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_benchmarks",
                    "description": "列出所有性能测试记录",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "evaluate_model",
                    "description": "根据测试数据评估模型性能，给出分析建议",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "bench_id": {"type": "string", "description": "测试ID"},
                        },
                        "required": ["bench_id"],
                    },
                },
            },
        ]

    async def chat(
        self,
        session_id: str,
        message: str,
        context_data: Optional[dict] = None,
    ) -> AsyncGenerator[str, None]:
        """Stream chat with function calling support."""
        if session_id not in self.conversations:
            self.conversations[session_id] = []

        conv = self.conversations[session_id]

        # Build system prompt with context
        system_prompt = (
            "你是vLLM Dashboard平台的AI助手，可以帮助用户管理集群、启动模型、运行测试。"
            "你可以使用function calling来执行操作。回答简洁专业。"
        )
        if context_data:
            system_prompt += f"\n\n当前平台状态:\n{json.dumps(context_data, ensure_ascii=False, indent=2)}"

        conv.append({"role": "user", "content": message})

        api_url, model_name, api_key = self._get_effective_config()
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{api_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json={
                        "model": model_name,
                        "messages": [{"role": "system", "content": system_prompt}] + conv[-20:],
                        "tools": self._get_tools(),
                        "tool_choice": "auto",
                        "stream": True,
                    },
                )
                resp.raise_for_status()

                full_content = ""
                tool_calls_acc: Dict[int, dict] = {}

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk["choices"][0]["delta"]

                        if delta.get("content"):
                            full_content += delta["content"]
                            yield json.dumps({"type": "text", "content": delta["content"]})

                        if delta.get("tool_calls"):
                            for tc in delta["tool_calls"]:
                                idx = tc["index"]
                                if idx not in tool_calls_acc:
                                    tool_calls_acc[idx] = {
                                        "id": tc.get("id", ""),
                                        "function": {"name": "", "arguments": ""},
                                    }
                                if tc.get("id"):
                                    tool_calls_acc[idx]["id"] = tc["id"]
                                if tc.get("function", {}).get("name"):
                                    tool_calls_acc[idx]["function"]["name"] += tc["function"]["name"]
                                if tc.get("function", {}).get("arguments"):
                                    tool_calls_acc[idx]["function"]["arguments"] += tc["function"]["arguments"]
                    except json.JSONDecodeError:
                        continue

                # Execute tool calls
                if tool_calls_acc:
                    for tc in sorted(tool_calls_acc.values(), key=lambda x: x["id"]):
                        func_name = tc["function"]["name"]
                        try:
                            args = json.loads(tc["function"]["arguments"])
                        except json.JSONDecodeError:
                            args = {}

                        yield json.dumps({"type": "tool_call", "name": func_name, "args": args})

                        result = await self._execute_tool(func_name, args)
                        yield json.dumps({"type": "tool_result", "name": func_name, "result": result})

                        conv.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": func_name, "arguments": json.dumps(args)},
                            }],
                        })
                        conv.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result, ensure_ascii=False),
                        })

                    # Get final response after tool calls
                    resp2 = await client.post(
                        f"{api_url.rstrip('/')}/chat/completions",
                        headers=headers,
                        json={
                            "model": model_name,
                            "messages": [{"role": "system", "content": system_prompt}] + conv[-25:],
                            "stream": True,
                        },
                    )
                    resp2.raise_for_status()
                    async for line in resp2.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            content = chunk["choices"][0]["delta"].get("content", "")
                            if content:
                                yield json.dumps({"type": "text", "content": content})
                        except json.JSONDecodeError:
                            continue

                if full_content:
                    conv.append({"role": "assistant", "content": full_content})

        except Exception as e:
            yield json.dumps({"type": "error", "content": f"AI服务错误: {str(e)}"})

    async def _execute_tool(self, name: str, args: dict) -> dict:
        """Execute platform control functions."""
        try:
            from services.docker_service import docker_service
            from services.vllm_service import vllm_service
            from services.api_bench_service import api_bench_service as abs

            if name == "list_clusters":
                clusters = await docker_service.list_clusters()
                return {"clusters": clusters}

            elif name == "list_models":
                models = await vllm_service.list_models()
                return {"models": models}

            elif name == "list_benchmarks":
                vllm_b = await vllm_service.list_benchmarks()
                api_b = abs.list_benchmarks()
                return {"benchmarks": vllm_b + api_b}

            elif name == "create_cluster":
                cluster = await docker_service.create_cluster(
                    name=args.get("name", "ai-cluster"),
                    head_nodes=args.get("head_nodes", 1),
                    worker_nodes=args.get("worker_nodes", 0),
                    gpu_per_node=args.get("gpu_per_node", 1),
                )
                return {"cluster": cluster}

            elif name == "start_model":
                model_id = await vllm_service.start_model(
                    cluster_id=args["cluster_id"],
                    model_path=args["model_path"],
                    model_name=args.get("model_name", args["model_path"].split("/")[-1]),
                    tensor_parallel_size=args.get("tensor_parallel_size", 1),
                )
                return {"model_id": model_id}

            elif name == "run_benchmark":
                bench_id = await vllm_service.run_benchmark_v2(
                    model_path=args["model_path"],
                    tokenizer_path=args.get("model_path", ""),
                    random_input_len=args.get("input_len", 2048),
                    random_output_len=args.get("output_len", 2048),
                    num_prompts=args.get("num_prompts", 5),
                )
                return {"bench_id": bench_id}

            elif name == "evaluate_model":
                bench_id = args["bench_id"]
                bench_data = None
                if bench_id.startswith("api-bench-"):
                    bench_data = abs.get_benchmark(bench_id)
                else:
                    bench_data = await vllm_service.get_benchmark(bench_id)

                if not bench_data:
                    return {"error": "测试记录不存在"}

                # Build evaluation summary
                if bench_data.get("type") == "api":
                    return {
                        "evaluation": {
                            "model": bench_data.get("model_name"),
                            "avg_latency_ms": bench_data.get("avg_latency_ms"),
                            "p99_latency_ms": bench_data.get("p99_latency_ms"),
                            "qps": bench_data.get("requests_per_second"),
                            "tokens_per_second": bench_data.get("tokens_per_second"),
                            "success_rate": f"{bench_data.get('success_count', 0)}/{bench_data.get('total_requests', 0)}",
                            "analysis": (
                                f"该模型平均延迟{bench_data.get('avg_latency_ms', 0):.0f}ms，"
                                f"P99延迟{bench_data.get('p99_latency_ms', 0):.0f}ms，"
                                f"吞吐量{bench_data.get('tokens_per_second', 0):.0f} tokens/s。"
                            ),
                        }
                    }
                else:
                    metrics = bench_data.get("result", {}).get("metrics", {})
                    return {
                        "evaluation": {
                            "model": bench_data.get("model_name"),
                            "metrics": metrics,
                            "analysis": "vLLM本地模型测试结果，详见指标数据。",
                        }
                    }

            return {"error": f"未知操作: {name}"}

        except Exception as e:
            return {"error": str(e)}

    def clear_session(self, session_id: str):
        self.conversations.pop(session_id, None)


ai_chat_service = AIChatService()