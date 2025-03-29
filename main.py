from astrbot.api.all import *
import random
import requests
import os
import time
import shutil
import yaml

@register("poke_monitor", "Your Name", "监控戳一戳事件插件", "1.3.0")
class PokeMonitorPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.user_poke_timestamps = {}
        self.call_count = 0  # 调用计数器
        self.last_reset_time = time.time()  # 上次重置时间
        # 构建配置文件路径
        config_dir = os.path.join("data", "plugins", "astrbot_plugin_pock")
        config_path = os.path.join(config_dir, "config.yml")

        # 检查配置文件是否存在，若不存在则创建并写入默认值
        if not os.path.exists(config_path):
            self._create_default_config(config_path)

        try:
            # 读取配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            self.poke_responses = self.config.get('poke_responses', [])
            self.emoji_url_mapping = self.config.get('emoji_url_mapping', {})
            self.random_emoji_trigger_probability = self.config['random_emoji_trigger_probability']
            self.feature_switches = self.config.get('feature_switches', {})
            self.poke_back_probability = self.config['poke_back_probability']
            self.super_poke_probability = self.config['super_poke_probability']
        except FileNotFoundError:
            pass
        except Exception as e:
            pass

        self._clean_legacy_directories()
        self._clean_emoji_directory()  # 添加此行以在启动时清理表情包目录

    def _create_default_config(self, config_path):
        """创建默认配置文件"""
        default_config = {
            # 戳一戳回复消息
            "poke_responses": [
                "别戳啦！",
                "哎呀，还戳呀，别闹啦！",
                "别戳我啦  你要做什么  不理你了"
            ],
            # 表情包 API 映射
            "emoji_url_mapping": {
                "咬": "https://api.lolimi.cn/API/face_suck/api.php",
                "捣": "https://api.lolimi.cn/API/face_pound/api.php",
                "玩": "https://api.lolimi.cn/API/face_play/api.php",
                "拍": "https://api.lolimi.cn/API/face_pat/api.php",
                "丢": "https://api.lolimi.cn/API/diu/api.php",
                "撕": "https://api.lolimi.cn/API/si/api.php",
                "爬": "https://api.lolimi.cn/API/pa/api.php"
            },
            # 随机触发表情包的概率
            "random_emoji_trigger_probability": 0,
            # 功能开关
            "feature_switches": {
                "poke_response_enabled": True,
                "poke_back_enabled": True,
                "emoji_trigger_enabled": True
            },
            # 戳 Bot 反击相关概率
            "poke_back_probability": 0.8,
            "super_poke_probability": 0.6
        }
        # 创建配置文件所在目录
        config_dir = os.path.dirname(config_path)
        os.makedirs(config_dir, exist_ok=True)
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(default_config, f, allow_unicode=True, default_flow_style=False)
        except Exception as e:
            pass

    def _clean_legacy_directories(self):
        """安全清理旧目录（仅删除特定目录）"""
        legacy_dirs = [
            os.path.abspath("./data/plugins/poke_monitor"),  # 旧版本目录
            os.path.abspath("./data/plugins/plugins/poke_monitor")  # 防止误删其他插件
        ]

        for path in legacy_dirs:
            try:
                if os.path.exists(path):
                    shutil.rmtree(path)
            except Exception as e:
                pass

    def _clean_emoji_directory(self):
        """清理表情包目录下的所有图片"""
        save_dir = os.path.join("data", "plugins", "astrbot_plugin_pock", "poke_monitor")
        if os.path.exists(save_dir):
            for filename in os.listdir(save_dir):
                file_path = os.path.join(save_dir, filename)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    pass

    @event_message_type(EventMessageType.GROUP_MESSAGE)
    async def on_group_message(self, event: AstrMessageEvent):
        now = time.time()
        if now - self.last_reset_time > 60:
            self.call_count = 0
            self.last_reset_time = now

        self.call_count += 1
        if self.call_count > 5:
            return  # 超过调用次数限制，终止调用

        message_obj = event.message_obj
        raw_message = message_obj.raw_message
        is_super = False  # 超级加倍标志

        if raw_message.get('post_type') == 'notice' and \
                raw_message.get('notice_type') == 'notify' and \
                raw_message.get('sub_type') == 'poke':
            bot_id = raw_message.get('self_id')
            sender_id = raw_message.get('user_id')
            target_id = raw_message.get('target_id')

            now = time.time()
            three_minutes_ago = now - 3 * 60

            # 清理旧记录
            if sender_id in self.user_poke_timestamps:
                self.user_poke_timestamps[sender_id] = [
                    t for t in self.user_poke_timestamps[sender_id] if t > three_minutes_ago
                ]

            if bot_id and sender_id and target_id:
                # 用户戳机器人
                if str(target_id) == str(bot_id):
                    # 记录戳一戳
                    if sender_id not in self.user_poke_timestamps:
                        self.user_poke_timestamps[sender_id] = []
                    self.user_poke_timestamps[sender_id].append(now)

                    # 文本回复
                    if self.feature_switches.get('poke_response_enabled', True):
                        poke_count = len(self.user_poke_timestamps[sender_id])
                        if poke_count < 4:
                            response = self.poke_responses[poke_count - 1] if poke_count <= len(self.poke_responses) else self.poke_responses[-1]
                            yield event.plain_result(response)

                    # 概率戳回
                    if self.feature_switches.get('poke_back_enabled', True) and random.random() < self.poke_back_probability:
                        if random.random() < self.super_poke_probability:
                            poke_times = 10
                            yield event.plain_result("喜欢戳是吧")
                            is_super = True
                        else:
                            poke_times = 1
                            yield event.plain_result("戳戳你的")

                        # 发送戳一戳
                        if event.get_platform_name() == "aiocqhttp":
                            from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                            assert isinstance(event, AiocqhttpMessageEvent)
                            client = event.bot
                            group_id = raw_message.get('group_id')
                            payloads = {"user_id": sender_id}
                            if group_id:
                                payloads["group_id"] = group_id
                            for _ in range(poke_times):
                                try:
                                    await client.api.call_action('send_poke', **payloads)
                                except Exception as e:
                                    pass

                # 用户戳其他人（且不是机器人自己触发的）
                elif str(sender_id) != str(bot_id):  
                    # 随机触发表情包
                    if self.feature_switches.get('emoji_trigger_enabled', True) and random.random() < self.random_emoji_trigger_probability:
                        available_actions = list(self.emoji_url_mapping.keys())
                        selected_action = random.choice(available_actions)

                        url = self.emoji_url_mapping.get(selected_action)
                        params = {'QQ': target_id}

                        # 硬编码请求配置
                        timeout = 10
                        max_retries = 3
                        retry_count = 0
                        while retry_count < max_retries:
                            try:
                                response = requests.get(url, params=params, timeout=timeout)
                                if response.status_code == 200:
                                    # 跨平台安全路径
                                    save_dir = os.path.join("data", "plugins", "astrbot_plugin_pock", "poke_monitor")
                                    os.makedirs(save_dir, exist_ok=True)

                                    # 唯一文件名防止冲突
                                    filename = f"{selected_action}_{target_id}_{int(time.time())}.gif"
                                    image_path = os.path.join(save_dir, filename)

                                    with open(image_path, "wb") as f:
                                        f.write(response.content)
                                    yield event.image_result(image_path)

                                    # 在发送成功后删除图片
                                    if os.path.exists(image_path):
                                        try:
                                            os.remove(image_path)
                                        except Exception as e:
                                            pass
                                    break
                                else:
                                    yield event.plain_result(f"表情包请求失败，状态码：{response.status_code}")
                                    break
                            except requests.exceptions.ReadTimeout:
                                retry_count += 1
                                if retry_count == max_retries:
                                    yield event.plain_result(f"表情包处理出错：多次请求超时，无法获取数据。")
                            except Exception as e:
                                yield event.plain_result(f"表情包处理出错：{str(e)}")
                                break
