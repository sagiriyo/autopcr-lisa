import os, io, re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
from PIL import Image, ImageFont, ImageDraw
from ..constants import DATA_DIR, CACHE_DIR
from .draw_table import grid2img, json2img
from pathlib import Path
from ..db.imagemgr import instance as imgmgr

if TYPE_CHECKING:
    from ..mzq.mzq import UnitDTO

JJC_IMAGE_PATH = os.path.join(CACHE_DIR, "jjc_image")
STAR_IMAGE_PATH = os.path.join(JJC_IMAGE_PATH, "star")
UNIQUE_EQ_IMAGE_PATH = os.path.join(JJC_IMAGE_PATH, "uniqueEq")
ROLE_IMAGE_PATH = os.path.join(JJC_IMAGE_PATH, "role")
TALENT_IMAGE_PATH = os.path.join(JJC_IMAGE_PATH, "talent")
JJC_FOOTER_HEIGHT = 46


@dataclass
class DrawUnit:
    unitId: int
    rarity: int
    exEquip: List[int]
    uniqueEqLv: int = 0
    uniqueEq2Lv: int = -1
    unitRoleId: int = 0
    talentId: int = 0


def resolve_unit_role_talent_ids(unit_id: int) -> Tuple[int, int]:
    role_id = 0
    talent_id = 0
    try:
        from ..db.database import db

        base_unit_id = unit_id // 100 if unit_id > 100000 else unit_id
        for candidate in (unit_id, base_unit_id, base_unit_id * 100 + 1):
            if role_id <= 0:
                role_id = int(db.unit_role_data.get(candidate, 0) or 0)
            if talent_id <= 0:
                talent_id = int(db.unit_talent.get(candidate, 0) or 0)
            if role_id > 0 and talent_id > 0:
                break
    except Exception:
        pass
    return role_id, talent_id


class Drawer():  
  
    font_path = os.path.join(DATA_DIR, "微软雅黑.ttf")  
    font=ImageFont.truetype(font_path, size=30)  
  
    def dark_color(self):  
        return {  
            'bg': '#222529',  
            'odd_row_cell_bg': '#3A3A3C',  
            'even_row_cell_bg': '#2C2C2E',  
            'header_bg': '#1C1C1E',  
            'font': '#DFE2E6',  
            'rowline': 'white',  
            'colline': 'white',  
            '成功': '#255035',  
            '跳过': '#35778D',  
            '警告': '#FF8C00',  
            '中止': '#937526',  
            '错误': '#79282C',  
            '致命': '#8B0000',  
        }  
  
    def light_color(self):  
        return {  
            'bg': 'white',  
            'odd_row_cell_bg': '#EEEEEE',  
            'even_row_cell_bg': 'white',  
            'header_bg': '#C8C8C9',  
            'font': 'black',  
            'rowline': 'black',  
            'colline': 'black',  
            '成功': '#E1FFB5',  
            '跳过': '#C8D6FA',  
            '警告': '#FFD700',  
            '中止': 'yellow',  
            '错误': 'red',  
            '致命': '#8B0000',  
        }  
  
    def color(self):  
        from datetime import datetime  
        now = datetime.now()  
        is_night = not(now.hour < 18 and now.hour > 7)  
        if is_night:  
            return self.dark_color()  
        else:  
            return self.light_color()  
  
    async def draw(self, header: List[str], content: List[List[str]]) -> Image.Image:  
        img = grid2img(content, header, colors=self.color(), font=self.font, stock=True)  
        return img  
  
    async def draw_json(self, titles: List[str], records: List[Dict]) -> Image.Image:  
        img = json2img(records, titles, colors=self.color(), font=self.font, stock=True)  
        return img  
  
    #过滤了跳过的内容
    async def draw_tasks_result(self, data: "TaskResult", skip_skipped: bool = False) -> Image.Image:  
        content = []  
        header = ["序号", "名字","配置","状态","结果"]  
        result = data.result  
        cnt = 0  
        for key in data.order:  
            value = result[key]  
            if value.log == "功能未启用":  
                continue  
            if skip_skipped and value.status.value == "跳过":  
                continue  
            cnt += 1  
            content.append([str(cnt), value.name.strip(), value.config.strip(), "#"+value.status.value, value.log.strip()])  
        img = await self.draw(header, content)  
        return img
  
    async def draw_task_result(self, data: "ModuleResult") -> Image.Image:  
        # 「我的支援」：日志同时含 [unit: 和 [ex:，必须先判断 [unit:  
        if '[unit:' in data.log:  
            return await self.draw_my_support_result(data)  
        # 检测是否包含EX装备图标标记  
        if '[ex:' in data.log:  
            return await self.draw_ex_equip_result(data)
        if data.table and data.table.data and len(data.table.data) > 1:  
            return await self.draw_task_table(data)  
        content = [["配置", data.config.strip()], ["状态", f"#{data.status.value}"], ["结果", data.log.strip()]]  
        header = ["名字", data.name.strip()]  
        img = await self.draw(header, content)  
        return img  
  
    async def draw_ex_equip_result(self, data: "ModuleResult") -> Image.Image:  
        """渲染带EX装备图标的预览图"""  
  
        colors = self.color()  
        font = self.font  
  
        ICON_SIZE = 144  
        LINE_HEIGHT = max(ICON_SIZE + 8, 44)  
        HEADER_LINE_HEIGHT = 40  
        LEFT_MARGIN = 12  
        ICON_TEXT_GAP = 8  
        TOP_MARGIN = 10  
        RIGHT_MARGIN = 20  
  
        # 解析log，提取 [ex:XXXXXXX] 标记  
        log_text = data.log.strip()  
        raw_lines = log_text.split('\n')  
  
        ex_pattern = re.compile(r'^\[ex:(\d+)\](.*)')  
  
        parsed_lines = []  # list of (equip_id 或 None, 显示文本)  
        for line in raw_lines:  
            m = ex_pattern.match(line)  
            if m:  
                equip_id = int(m.group(1))  
                text = m.group(2)  
                parsed_lines.append((equip_id, text))  
            else:  
                parsed_lines.append((None, line))  
  
        # 加载图标（使用 imagemgr，会自动下载缓存）  
        icon_cache = {}  
        for equip_id, _ in parsed_lines:  
            if equip_id and equip_id not in icon_cache:  
                try:  
                    icon = await imgmgr.ex_equip_icon(equip_id)  
                    if icon:  
                        icon_cache[equip_id] = icon  
                except Exception:  
                    pass  
  
        # 头部信息（config 可能有多行，逐行拆分）  
        header_texts = [f"【{data.name.strip()}】"]  
        for line in data.config.strip().split('\n'):  
            line = line.strip()  
            if line:  
                header_texts.append(line)
  
        # 计算画布尺寸  
        dummy_img = Image.new('RGB', (1, 1))  
        dummy_draw = ImageDraw.Draw(dummy_img)  
  
        max_width = 0  
        for text in header_texts:  
            bbox = dummy_draw.textbbox((0, 0), text, font=font)  
            max_width = max(max_width, bbox[2] - bbox[0])  
  
        for equip_id, text in parsed_lines:  
            bbox = dummy_draw.textbbox((0, 0), text, font=font)  
            tw = bbox[2] - bbox[0]  
            line_width = LEFT_MARGIN + ICON_SIZE + ICON_TEXT_GAP + tw + RIGHT_MARGIN  
            max_width = max(max_width, line_width)  
  
        canvas_width = int(max_width + LEFT_MARGIN + RIGHT_MARGIN)  
        canvas_height = int(  
            TOP_MARGIN +  
            len(header_texts) * HEADER_LINE_HEIGHT +  
            10 +  
            len(parsed_lines) * LINE_HEIGHT +  
            TOP_MARGIN  
        )  
  
        bg_color = colors['bg']  
        font_color = colors['font']  
  
        canvas = Image.new('RGB', (canvas_width, canvas_height), bg_color)  
        draw = ImageDraw.Draw(canvas)  
  
        # 绘制头部  
        y = TOP_MARGIN  
        for text in header_texts:  
            draw.text((LEFT_MARGIN, y), text, font=font, fill=font_color)  
            y += HEADER_LINE_HEIGHT  
  
        # 分隔线  
        y += 5  
        draw.line([(LEFT_MARGIN, y), (canvas_width - RIGHT_MARGIN, y)], fill=font_color)  
        y += 5  
  
        # 绘制日志行（带图标）  
        for equip_id, text in parsed_lines:  
            icon_img = icon_cache.get(equip_id) if equip_id else None  
  
            if icon_img:  
                resized = icon_img.copy().resize(  
                    (ICON_SIZE, ICON_SIZE),  
                    Image.LANCZOS if hasattr(Image, 'LANCZOS') else Image.ANTIALIAS  
                )  
                icon_y = y + (LINE_HEIGHT - ICON_SIZE) // 2  
                if resized.mode == 'RGBA':  
                    canvas.paste(resized, (LEFT_MARGIN, icon_y), resized)  
                else:  
                    canvas.paste(resized, (LEFT_MARGIN, icon_y))  
                text_x = LEFT_MARGIN + ICON_SIZE + ICON_TEXT_GAP  
            else:  
                # 没有图标的行，文本也从同一位置开始（保持对齐）  
                text_x = LEFT_MARGIN + ICON_SIZE + ICON_TEXT_GAP  
  
            bbox = draw.textbbox((0, 0), text, font=font)  
            text_h = bbox[3] - bbox[1]  
            text_y = y + (LINE_HEIGHT - text_h) // 2  
            draw.text((text_x, text_y), text, font=font, fill=font_color)  
            y += LINE_HEIGHT  
  
        return canvas  
  
    async def draw_my_support_result(self, data: "ModuleResult") -> Image.Image:  
        """我的支援：同类角色横向并列，角色直接转头像，下面纵向列出其EX装备"""  
        colors = self.color()  
        font = self.font  
        name_font = ImageFont.truetype(self.font_path, size=22)  
        ex_font = ImageFont.truetype(self.font_path, size=22)  
  
        AVATAR_SIZE = 96  
        EX_ICON_SIZE = 56  
        EX_TEXT_GAP = 6  
        EX_LINE_HEIGHT = EX_ICON_SIZE + 6  
        CARD_PADDING = 12  
        CARD_GAP = 16  
        CAT_TITLE_HEIGHT = 46  
        NAME_HEIGHT = 30  
        TOP_MARGIN = 12  
        LEFT_MARGIN = 16  
        ROW_GAP = 18  
  
        cat_pattern = re.compile(r'^【(.*)】$')  
        unit_pattern = re.compile(r'^\[unit:(\d+)\](.*)')  
        ex_pattern = re.compile(r'^\[ex:(\d+)\](.*)')  
  
        # 解析成 分类 -> 角色 -> EX 三层结构  
        categories = []  
        cur_cat = None  
        cur_char = None  
        for raw in data.log.strip().split('\n'):  
            line = raw.strip()  
            if not line:  
                continue  
            mc = cat_pattern.match(line)  
            mu = unit_pattern.match(line)  
            me = ex_pattern.match(line)  
            if mc:  
                cur_cat = {"title": mc.group(1), "chars": [], "empty": None}  
                categories.append(cur_cat)  
                cur_char = None  
            elif mu:  
                cur_char = {"unit_id": int(mu.group(1)), "exs": []}  
                if cur_cat is not None:  
                    cur_cat["chars"].append(cur_char)  
            elif me:  
                if cur_char is not None:  
                    cur_char["exs"].append((int(me.group(1)), me.group(2).strip()))  
            else:  
                if cur_cat is not None and not cur_cat["chars"]:  
                    cur_cat["empty"] = line  
  
        # 从 db 取角色名（不依赖日志文本）  
        from ..db.database import db  
  
        # 预加载头像与EX图标  
        unit_icons, ex_icons = {}, {}  
        for cat in categories:  
            for ch in cat["chars"]:  
                uid = ch["unit_id"]  
                if uid not in unit_icons:  
                    try:  
                        ic = await imgmgr.unit_icon(uid)  
                        if ic:  
                            unit_icons[uid] = ic  
                    except Exception:  
                        pass  
                for ex_id, _ in ch["exs"]:  
                    if ex_id not in ex_icons:  
                        try:  
                            ic = await imgmgr.ex_equip_icon(ex_id)  
                            if ic:  
                                ex_icons[ex_id] = ic  
                        except Exception:  
                            pass  
  
        dummy = ImageDraw.Draw(Image.new('RGB', (1, 1)))  
        def text_w(txt, f):  
            b = dummy.textbbox((0, 0), txt, font=f)  
            return b[2] - b[0]  
  
        def card_size(ch):  
            name = db.get_unit_name(ch["unit_id"])  
            max_ex_text = 0  
            for _, t in ch["exs"]:  
                max_ex_text = max(max_ex_text, text_w(t, ex_font))  
            content_w = max(AVATAR_SIZE, text_w(name, name_font),  
                            EX_ICON_SIZE + EX_TEXT_GAP + max_ex_text)  
            w = CARD_PADDING * 2 + content_w  
            ex_h = max(1, len(ch["exs"])) * EX_LINE_HEIGHT  
            h = CARD_PADDING * 2 + AVATAR_SIZE + NAME_HEIGHT + ex_h  
            return w, h  
  
        # 布局计算  
        canvas_width = 220  
        row_infos = []  
        for cat in categories:  
            if cat["chars"]:  
                widths, row_h = [], 0  
                for ch in cat["chars"]:  
                    w, h = card_size(ch)  
                    widths.append(w)  
                    row_h = max(row_h, h)  
                row_w = LEFT_MARGIN * 2 + sum(widths) + CARD_GAP * (len(widths) - 1)  
                canvas_width = max(canvas_width, row_w)  
                row_infos.append((cat, row_h, widths))  
            else:  
                row_infos.append((cat, 44, []))  
            canvas_width = max(canvas_width, LEFT_MARGIN * 2 + text_w(f"【{cat['title']}】", font))  
  
        canvas_height = TOP_MARGIN  
        for (_, row_h, _) in row_infos:  
            canvas_height += CAT_TITLE_HEIGHT + row_h + ROW_GAP  
  
        canvas = Image.new('RGB', (int(canvas_width), int(canvas_height)), colors['bg'])  
        draw = ImageDraw.Draw(canvas)  
        font_color = colors['font']  
        resample = Image.LANCZOS if hasattr(Image, 'LANCZOS') else Image.ANTIALIAS  
  
        y = TOP_MARGIN  
        for (cat, row_h, widths) in row_infos:  
            draw.text((LEFT_MARGIN, y + 6), f"【{cat['title']}】", font=font, fill=font_color)  
            y += CAT_TITLE_HEIGHT  
            if not cat["chars"]:  
                draw.text((LEFT_MARGIN + 12, y), cat["empty"] or "无", font=name_font, fill=font_color)  
                y += row_h + ROW_GAP  
                continue  
            # 每个分类按角色数等分成 N 个等宽格子，卡片在各自格子内居中  
            n = len(cat["chars"])  
            cell_w = canvas_width // n  
            for i, (ch, cw) in enumerate(zip(cat["chars"], widths)):  
                cell_x = i * cell_w  
                card_x = cell_x + (cell_w - cw) // 2   # 卡片在格子内居中  
                # 头像（在卡片内居中）  
                av = unit_icons.get(ch["unit_id"])  
                av_x = card_x + (cw - AVATAR_SIZE) // 2  
                if av:  
                    r = av.copy().resize((AVATAR_SIZE, AVATAR_SIZE), resample)  
                    if r.mode == 'RGBA':  
                        canvas.paste(r, (av_x, y + CARD_PADDING), r)  
                    else:  
                        canvas.paste(r, (av_x, y + CARD_PADDING))  
                # 角色名（db 取，画在头像下方）  
                name = db.get_unit_name(ch["unit_id"])  
                name_y = y + CARD_PADDING + AVATAR_SIZE + 2  
                nx = card_x + (cw - text_w(name, name_font)) // 2  
                draw.text((nx, name_y), name, font=name_font, fill=font_color)  
                # EX 装备（图标+文字，纵向）  
                ex_y = name_y + NAME_HEIGHT  
                ex_x = card_x + CARD_PADDING  
                if not ch["exs"]:  
                    draw.text((ex_x, ex_y), "无EX装备", font=ex_font, fill=font_color)  
                for ex_id, t in ch["exs"]:  
                    icon = ex_icons.get(ex_id)  
                    if icon:  
                        ri = icon.copy().resize((EX_ICON_SIZE, EX_ICON_SIZE), resample)  
                        if ri.mode == 'RGBA':  
                            canvas.paste(ri, (ex_x, ex_y), ri)  
                        else:  
                            canvas.paste(ri, (ex_x, ex_y))  
                    tb = draw.textbbox((0, 0), t, font=ex_font)  
                    th = tb[3] - tb[1]  
                    draw.text((ex_x + EX_ICON_SIZE + EX_TEXT_GAP, ex_y + (EX_ICON_SIZE - th) // 2),  
                              t, font=ex_font, fill=font_color)  
                    ex_y += EX_LINE_HEIGHT  
            y += row_h + ROW_GAP
  
        return canvas
    
    async def draw_task_table(self, data: "ModuleResult") -> Image.Image:  
        content = data.table.data  
        header = data.table.header  
        img = await self.draw_json(header, content)  
        return img  
  
    async def draw_msgs(self, msgs: List[str]) -> Image.Image:  
        content = [[msg] for msg in msgs]  
        img = await self.draw(["结果"], content)  
        return img  
  
    async def horizon_concatenate(self, images_path: List[str]):  
        images = [Image.open(i) for i in images_path]  
        widths, heights = zip(*(i.size  for i in images))  
  
        max_height = max(heights)  
        total_widths = sum(widths)  
  
        new_image = Image.new('RGB', (total_widths, max_height))  
  
        x_offset = 0  
        for img in images:  
            new_image.paste(img, (x_offset, 0))  
            x_offset += img.size[0]  
  
        return new_image  
      
    async def img2bytesio(self, img: Image.Image, format: str = 'JPEG') -> io.BytesIO:  
        img_byte_arr = io.BytesIO()  
        img.save(img_byte_arr, format=format)  
        img_byte_arr.seek(0)  
        return img_byte_arr  
  

    def _new_jjc_canvas(self, width: int, height: int, colors: dict) -> Image.Image:
        canvas = Image.new("RGB", (width, height + JJC_FOOTER_HEIGHT), colors["bg"])
        return canvas

    def _draw_jjc_frame(self, draw: ImageDraw.ImageDraw, im: Image.Image, colors: dict):
        width, height = im.size
        border_color = colors["rowline"]
        text_color = colors["font"]
        footer_top = max(0, height - JJC_FOOTER_HEIGHT)

        draw.line([(0, footer_top), (width, footer_top)], fill=border_color, width=1)
        draw.rectangle([0, 0, width - 1, height - 1], outline=border_color, width=2)
        if width > 6 and height > 6:
            draw.rectangle([4, 4, width - 5, height - 5], outline=border_color, width=1)

        text = "Power By PCRCalculator"
        footer_font = ImageFont.truetype(self.font_path, 20)
        l, t, r, b = footer_font.getbbox(text)
        tx = max(0, (width - (r - l)) / 2)
        ty = footer_top + max(0, (JJC_FOOTER_HEIGHT - (b - t)) / 2) - t
        draw.text((tx, ty), text, fill=text_color, font=footer_font)

    @staticmethod
    def _icon_file(icon_dir: str, icon_name: str) -> Optional[str]:
        candidates = [
            os.path.join(icon_dir, icon_name),
            os.path.join(icon_dir, f"{icon_name}.png"),
        ]
        return next((path for path in candidates if os.path.exists(path)), None)

    def _paste_overlay_icon(self, im: Image.Image, icon_file: Optional[str], x: int, y: int, size: Tuple[int, int]) -> bool:
        if not icon_file:
            return False
        try:
            icon = Image.open(icon_file).convert("RGBA").resize(size, Image.LANCZOS)
            im.paste(icon, (x, y), icon)
            return True
        except Exception:
            return False

    async def draw_unit_portrait(self, unit_id: int, rarity: int, icon_size: int = 82) -> Optional[Image.Image]:
        from ..db.imagemgr import instance as image_manager

        base_image = await image_manager.unit_icon(unit_id, rarity)
        if base_image is None:
            return None
        try:
            base_image.close()
        except Exception:
            pass

        role_id, talent_id = resolve_unit_role_talent_ids(unit_id)
        image = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
        await self._draw_unit_at(
            ImageDraw.Draw(image),
            image,
            DrawUnit(
                unitId=unit_id,
                rarity=rarity,
                exEquip=[],
                unitRoleId=role_id,
                talentId=talent_id,
            ),
            0,
            0,
            icon_size,
            0,
        )
        return image

    async def _draw_unit_at(self, draw: ImageDraw.ImageDraw, im: Image.Image, unit: DrawUnit, x: int, y: int, icon_size: int = 64, ex_size: int = 20):
        """Draws a single unit (icon + overlays + 3 EX equips) at the specified position."""
        from ..db.imagemgr import instance as image_manager

        uid = unit.unitId
        rarity = unit.rarity
        unique_eq_lv = unit.uniqueEqLv
        unique_eq2_lv = unit.uniqueEq2Lv
        role_id = unit.unitRoleId
        talent_id = unit.talentId
        colors = self.color()

        # 1. Draw Unit Icon
        if uid:
            u_img = await image_manager.unit_icon(uid, rarity)
            if u_img:
                u_img = u_img.resize((icon_size, icon_size))
                im.paste(u_img, (x, y))
            else:
                # Fallback: Draw Name
                try:
                    from ..db.database import db
                    unit_name = db.get_unit_name(uid)
                except Exception:
                    unit_name = f"未知角色({uid})"
                unit_name = f"{rarity}★" + unit_name if rarity and rarity > 0 else unit_name
                draw.rectangle([x, y, x + icon_size, y + icon_size], outline=colors['rowline'], fill=colors['bg'])

                f_size = 20
                f = ImageFont.truetype(self.font_path, f_size)
                # Shrink font until it fits
                while f.getlength(unit_name) > icon_size - 4 and f_size > 10:
                    f_size -= 2
                    f = ImageFont.truetype(self.font_path, f_size)

                l, t, r, b = f.getbbox(unit_name)
                # Center text
                tx = x + (icon_size - (r - l)) / 2
                ty = y + (icon_size - (b - t)) / 2 - t
                draw.text((tx, ty), unit_name, fill=colors['font'], font=f)

        # 2. Draw rarity, unique-equipment, talent and role overlays.
        # rarity_icon_file = self._icon_file(STAR_IMAGE_PATH, str(rarity)) if rarity > 0 else None
        # if rarity_icon_file:
        #     star_w = max(16, int(icon_size * 35 / 64))
        #     star_h = max(16, int(icon_size * 34 / 64))
        #     self._paste_overlay_icon(im, rarity_icon_file, x, y, (star_w, star_h))

        overlay_size = max(14, icon_size // 4)
        unique_icons: List[str] = []
        if unique_eq2_lv > 0:
            unique_icons.append("uniqueEq2")
        elif unique_eq_lv > 0:
            unique_icons.append("uniqueEq")
        for idx, icon_name in enumerate(unique_icons[:2]):
            icon_file = self._icon_file(UNIQUE_EQ_IMAGE_PATH, icon_name)
            icon_x = x + idx * overlay_size
            icon_y = y + icon_size - overlay_size
            self._paste_overlay_icon(im, icon_file, icon_x, icon_y, (overlay_size, overlay_size))

        has_talent = False
        if talent_id > 0:
            talent_file = self._icon_file(TALENT_IMAGE_PATH, str(talent_id))
            talent_x = x + icon_size - overlay_size
            talent_y = y + icon_size - overlay_size
            has_talent = self._paste_overlay_icon(im, talent_file, talent_x, talent_y, (overlay_size, overlay_size))

        if role_id > 0:
            role_file = self._icon_file(ROLE_IMAGE_PATH, str(role_id))
            role_x = x + icon_size - (2 * overlay_size if has_talent else overlay_size)
            role_y = y + icon_size - overlay_size
            self._paste_overlay_icon(im, role_file, role_x, role_y, (overlay_size, overlay_size))

        # 3. Draw EX Equips
        if ex_size <= 0:
            return

        # Positions: Left, Middle, Right
        positions = [0, (icon_size - ex_size) // 2, icon_size - ex_size]
        for i, ex_id in enumerate(unit.exEquip):
            if i >= 3: break
            ex_id = int(ex_id or 0)
            if ex_id > 0:
                ex_img = await image_manager.ex_equip_icon(ex_id)
                if ex_img:
                    ex_img = ex_img.resize((ex_size, ex_size))
                    # y + icon_size + 2 is the vertical position for EX icons
                    im.paste(ex_img, (x + positions[i], y + icon_size + 2))
                else:
                    # Fallback: Draw a colored square
                    draw.rectangle([x + positions[i], y + icon_size + 2, x + positions[i] + ex_size, y + icon_size + 2 + ex_size], outline=colors['rowline'], fill=colors['bg'])

                    try:
                        from ..db.database import db
                        ex_equip_name = db.get_ex_equip_name(ex_id)
                    except Exception:
                        ex_equip_name = str(ex_id)
                    f_size = 10
                    f = ImageFont.truetype(self.font_path, f_size)
                    # Shrink font until it fits
                    while f.getlength(ex_equip_name) > ex_size - 4 and f_size > 6:
                        f_size -= 1
                        f = ImageFont.truetype(self.font_path, f_size)
                    l, t, r, b = f.getbbox(ex_equip_name)
                    # Center text
                    tx = x + positions[i] + (ex_size - (r - l)) / 2
                    ty = y + icon_size + 2 + (ex_size - (b - t)) / 2 - t
                    draw.text((tx, ty), ex_equip_name, fill=colors['font'], font=f)

    @staticmethod
    def _header_info_lines(result) -> List[str]:
        p_info = result.player_info
        level = p_info[0].level if p_info else '-'
        rank = p_info[0].rank if p_info else '-'
        rank_slot = sum(1 for _ in p_info[0].equipLevel if _ >= 0) if p_info else '-'
        t_lvl = result.talent_level or '-'
        t_sk = result.talent_skill or '-'
        tm_sk = result.team_skill or '-'
        return [
            f"Lv{level}  R{rank}-{rank_slot}",
            f"{t_lvl}",
            f"{t_sk}",
            f"{tm_sk}",
        ]

    async def _draw_header_info(self, draw, font, result, x, y, line_height, align: str = "left", box_width: Optional[int] = None):
        """Draws the textual header info (Level, Rank, Talents). Returns new Y."""

        colors = self.color()
        font_color = colors['font']
        current_y = y
        lines = self._header_info_lines(result)

        def _draw_line(text: str):
            nonlocal current_y
            tx = x
            if align == "center" and box_width is not None:
                l, _t, r, _b = font.getbbox(text)
                tx = x + max(0, (box_width - (r - l)) / 2)
            draw.text((tx, current_y), text, fill=font_color, font=font)
            current_y += line_height

        for line in lines:
            _draw_line(line)

        return current_y

    async def _draw_unit_row(self, draw, im, units, y, align_right=False, canvas_width=800, margin=20, icon_size=64, unit_gap=6, ex_size=20):
        """Draws a row of units."""
        if not units:
            return
        draw_units = units if isinstance(units[0], DrawUnit) else self._normalize_units(units)
        if not draw_units:
            return

        n = len(draw_units)
        # Calculate total width of the row
        row_w = n * icon_size + (n - 1) * unit_gap

        start_x = (canvas_width - margin - row_w) if align_right else margin

        # When aligning right, we usually want the first unit in the list to be on the left of the block,
        # but the block is shifted to the right.
        # So we iterate normally from start_x.

        for idx, unit in enumerate(draw_units[::-1]):
            x = start_x + idx * (icon_size + unit_gap)
            await self._draw_unit_at(draw, im, unit, x, y, icon_size, ex_size)

    async def _draw_header_section(self, draw, im, first_result, defense_groups: List[List], colors: dict, canvas_width: int,
                                   margin=20, line_height=40, unit_block_h=84, team_gap=10):
        """Calculates height and draws the header + defense section."""
        header_text_h = 4 * line_height
        n_def = len(defense_groups)
        defense_h = n_def * unit_block_h + (n_def - 1) * team_gap

        # Total height: Margin + Text + Margin + Defense + Margin
        total_h = margin + header_text_h + margin + defense_h + margin

        if draw and im:
            # 1. Header Text Background (Top Margin + Text + Middle Margin)
            header_bg_h = margin + header_text_h + margin
            draw.rectangle([0, 0, canvas_width, header_bg_h], fill=colors['header_bg'])

            cy = margin
            if first_result:
                # Text Info
                cy = await self._draw_header_info(draw, self.font, first_result, margin, cy, line_height)
                cy += margin

                # Defense Rows
                draw.rectangle([0, cy, canvas_width, cy + (unit_block_h + team_gap) * len(defense_groups)], fill=colors['even_row_cell_bg'])
                for i, units in enumerate(defense_groups):
                    # Alternating Background

                    await self._draw_unit_row(draw, im, units, cy, align_right=True, canvas_width=canvas_width)
                    cy += unit_block_h + team_gap

        return total_h

    async def draw_pjjc_suggestion(self, results: List[List['JJCRecord']]) -> Image.Image:
        colors = self.color()
        if not results:
            return Image.new('RGB', (100, 100), colors['bg'])

        # Constants
        icon_size, ex_size = 64, 20
        unit_block_h = icon_size + ex_size
        unit_gap, team_gap, group_gap = 6, 10, 40
        line_height, margin = 40, 20

        text_start_x = margin + 5 * (icon_size + unit_gap) + 20

        # Calculate Width
        max_desc_w = 0
        for group in results:
            for rec in group:
                desc = rec.description(include_attack=False, include_defend=False)
                w = self.font.getlength(desc)
                if w > max_desc_w: max_desc_w = w
        canvas_width = max(800, int(text_start_x + max_desc_w + margin))

        # Data Preparation
        first_group = results[0]
        # Collect defense units for all teams in the first group
        def_groups_units = []
        for rec in first_group:
            def_groups_units.append((rec.results[0].enemy_info or []) if (rec.results) else [])

        first_result = first_group[0].results[0] if (first_group and first_group[0].results) else None

        # --- Height Calculation ---
        header_area_h = await self._draw_header_section(None, None, first_result, def_groups_units, colors, canvas_width,
                                                        margin, line_height, unit_block_h, team_gap)

        # Attack Groups Height
        groups_h = 0
        for i, group in enumerate(results):
            n_teams = len(group)
            group_h = n_teams * unit_block_h + (n_teams - 1) * team_gap
            groups_h += group_h
            if i < len(results) - 1:
                groups_h += group_gap

        content_height = header_area_h + groups_h + margin
        im = self._new_jjc_canvas(canvas_width, content_height, colors)
        draw = ImageDraw.Draw(im)

        # --- Drawing ---

        # 1. Header & Defense
        await self._draw_header_section(draw, im, first_result, def_groups_units, colors, canvas_width,
                                        margin, line_height, unit_block_h, team_gap)

        cy = header_area_h

        # 2. Attack Groups
        for i, group in enumerate(results):
            # Calculate group height
            n_teams = len(group)
            group_h = n_teams * unit_block_h + (n_teams - 1) * team_gap

            # Draw Background for this group
            bg_color = colors['odd_row_cell_bg'] if i % 2 == 0 else colors['even_row_cell_bg']
            draw.rectangle([0, cy, canvas_width, cy + group_h], fill=bg_color)

            for j, rec in enumerate(group):
                units = (rec.results[0].player_info or []) if (rec.results and rec.results[0].player_info) else []
                await self._draw_unit_row(draw, im, units, cy, align_right=False, canvas_width=canvas_width)

                # Description
                desc = rec.description(include_attack=False, include_defend=False)
                draw.text((text_start_x, cy + 20), desc, fill=colors['font'], font=self.font)

                cy += unit_block_h
                if j < len(group) - 1:
                     cy += team_gap

            if i < len(results) - 1:
                cy += group_gap

        self._draw_jjc_frame(draw, im, colors)
        return im

    async def draw_jjc_suggestion(self, results: List['JJCRecord']) -> Image.Image:
        if not results: return Image.new('RGB', (100, 100), 'white')

        colors = self.color()
        icon_size, ex_size = 64, 20
        unit_block_h = icon_size + ex_size
        unit_gap, row_gap = 6, 10
        line_height, margin = 40, 20

        # Data
        first_result = results[0].results[0] if (results and results[0].results) else None
        def_groups = [first_result.enemy_info or []] if first_result else []

        # Width
        text_start_x = margin + 5 * (icon_size + unit_gap) + 20
        max_desc_w = 0
        for rec in results:
             desc = rec.description(include_attack=False, include_defend=False)
             w = self.font.getlength(desc)
             if w > max_desc_w: max_desc_w = w
        canvas_width = max(800, int(text_start_x + max_desc_w + margin))

        # Height
        header_area_h = await self._draw_header_section(None, None, first_result, def_groups, colors, canvas_width,
                                                        margin, line_height, unit_block_h)
        attack_h = len(results) * (unit_block_h + row_gap)

        content_height = header_area_h + attack_h + margin
        im = self._new_jjc_canvas(canvas_width, content_height, colors)
        draw = ImageDraw.Draw(im)

        # Draw Header
        await self._draw_header_section(draw, im, first_result, def_groups, colors, canvas_width,
                                        margin, line_height, unit_block_h)

        cy = header_area_h

        # Draw Rows
        for i, rec in enumerate(results):
            bg_color = colors['odd_row_cell_bg'] if i % 2 == 0 else colors['even_row_cell_bg']

            # Row height includes the gap? Usually yes for visual block.
            draw.rectangle([0, cy, canvas_width, cy + unit_block_h + row_gap], fill=bg_color)

            units = (rec.results[0].player_info or []) if (rec.results and rec.results[0].player_info) else []
            await self._draw_unit_row(draw, im, units, cy, align_right=False, canvas_width=canvas_width)

            desc = rec.description(include_attack=False, include_defend=False)
            draw.text((text_start_x, cy + 20), desc, fill=colors['font'], font=self.font)

            cy += unit_block_h + row_gap

        self._draw_jjc_frame(draw, im, colors)
        return im


    async def draw_jjc_vs(self, results: List['JJCResult']) -> Image.Image:
        if not results: return Image.new('RGB', (100, 100), 'white')

        first = results[0]
        colors = self.color()

        icon_size, ex_size = 64, 20
        unit_block_h = icon_size + ex_size
        line_height, margin = 40, 20
        canvas_width = 800

        # Data
        def_groups = [first.enemy_info or []]

        # Height
        header_area_h = await self._draw_header_section(None, None, first, def_groups, colors, canvas_width,
                                                        margin, line_height, unit_block_h)
        attack_h = unit_block_h + margin
        results_h = len(results) * line_height

        content_height = header_area_h + attack_h + results_h + margin
        im = self._new_jjc_canvas(canvas_width, content_height, colors)
        draw = ImageDraw.Draw(im)

        # Draw Header
        await self._draw_header_section(draw, im, first, def_groups, colors, canvas_width,
                                        margin, line_height, unit_block_h)
        cy = header_area_h

        # Attack (Self)
        player_units = first.player_info or []
        await self._draw_unit_row(draw, im, player_units, cy, align_right=False, canvas_width=canvas_width)
        cy += unit_block_h + margin

        # Results List
        for idx, res in enumerate(results):
            bg_color = colors['odd_row_cell_bg'] if idx % 2 == 0 else colors['even_row_cell_bg']
            draw.rectangle([0, cy, canvas_width, cy + line_height], fill=bg_color)

            status = res.result
            if hasattr(status, 'name'):
                s_str = status.name
            else:
                m = {0: 'WIN', 1: 'LOSS', 2: 'TIMEOUT', 3:'UNKNOWN'}
                s_str = m.get(int(status), str(status))

            color = colors['font']
            s_up = s_str.upper()
            if 'WIN' in s_up: color = 'green'
            elif 'LOSS' in s_up or 'LOST' in s_up: color = 'red'
            elif 'TIMEOUT' in s_up: color = 'orange'

            text = f"{s_str:<10} Time: {res.duration:8.2f}s   Seed: {res.seed}"
            draw.text((margin, cy), text, fill=color, font=self.font)
            cy += line_height

        self._draw_jjc_frame(draw, im, colors)
        return im

    @staticmethod
    def _unit_from_obj(unit: "UnitDTO") -> Optional[DrawUnit]:
        unit_id = int(unit.unitId or 0)
        if unit_id <= 0:
            return None
        rarity = int(unit.rarity or 0)
        ex_equip = unit.exEquip or [0, 0, 0]
        if len(ex_equip) < 3:
            ex_equip = list(ex_equip) + [0] * (3 - len(ex_equip))

        role_id, talent_id = resolve_unit_role_talent_ids(unit_id)

        unique_eq2_value = unit.uniqueEq2Lv
        return DrawUnit(
            unitId=unit_id,
            rarity=rarity,
            exEquip=list(ex_equip[:3]),
            uniqueEqLv=int(unit.uniqueEqLv or 0),
            uniqueEq2Lv=int(unique_eq2_value if unique_eq2_value is not None else -1),
            unitRoleId=role_id,
            talentId=talent_id,
        )

    @classmethod
    def _normalize_units(cls, units: Optional[List["UnitDTO"]], limit: int = 5) -> List[DrawUnit]:
        if not units:
            return []
        normalized: List[DrawUnit] = []
        for unit in units[:limit]:
            parsed = cls._unit_from_obj(unit)
            if parsed is not None:
                normalized.append(parsed)
        return normalized

    async def _draw_blind_matrix_common(
        self,
        attack_groups: List[List[List[Any]]],
        group_matrices: List[List[List[float]]],
        defend_units: List[List[Any]],
        header_result: Optional['JJCResult'] = None,
        title: Optional[str] = None,
        row_group_gap: int = 0,
        group_left_labels: Optional[List[str]] = None,
    ) -> Image.Image:
        colors = self.color()
        if not attack_groups or not defend_units or not group_matrices:
            return Image.new("RGB", (400, 200), colors["bg"])

        n_groups = min(len(attack_groups), len(group_matrices))
        if n_groups <= 0:
            return Image.new("RGB", (400, 200), colors["bg"])

        attack_groups = attack_groups[:n_groups]
        group_matrices = group_matrices[:n_groups]
        group_left_labels = group_left_labels[:n_groups] if group_left_labels else None

        row_col_sizes: List[int] = []
        for rows in group_matrices:
            for row in rows:
                row_col_sizes.append(len(row))
        if not row_col_sizes:
            return Image.new("RGB", (400, 200), colors["bg"])
        n_cols = min(len(defend_units), min(row_col_sizes))
        if n_cols <= 0:
            return Image.new("RGB", (400, 200), colors["bg"])

        defend_units = defend_units[:n_cols]
        normalized_groups: List[List[List[Any]]] = []
        normalized_matrices: List[List[List[float]]] = []
        normalized_labels: List[str] = []
        for idx, (units_group, rows_group) in enumerate(zip(attack_groups, group_matrices)):
            if not units_group:
                continue
            if not rows_group:
                rows_group = [[(0, 0, 0, False)] * n_cols for _ in units_group]
            row_count = min(len(units_group), len(rows_group))
            if row_count <= 0:
                continue
            normalized_groups.append(units_group[:row_count])
            normalized_matrices.append([row[:n_cols] for row in rows_group[:row_count]])
            if group_left_labels and idx < len(group_left_labels):
                normalized_labels.append(group_left_labels[idx])
            else:
                normalized_labels.append("")

        if not normalized_groups:
            return Image.new("RGB", (400, 200), colors["bg"])

        # Layout
        margin = 20
        has_title = bool(title and title.strip())
        title_h = 42 if has_title else 0
        title_gap = 8 if has_title else 0
        icon_size = 52
        icon_gap = 6
        team_w = 5 * icon_size + 4 * icon_gap
        team_panel_w = team_w + 24
        label_font = ImageFont.truetype(self.font_path, 18)
        label_panel_w = 0
        if any(normalized_labels):
            max_label_w = 0
            for text in normalized_labels:
                if not text:
                    continue
                for line in text.splitlines() or [text]:
                    l, t, r, b = label_font.getbbox(line)
                    max_label_w = max(max_label_w, r - l)
            label_panel_w = max(72, max_label_w + 14)
        left_panel_w = label_panel_w + team_panel_w

        cell_w = max(74, icon_size + 18)
        cell_h = icon_size + 10
        team_col_h = 5 * icon_size + 4 * icon_gap
        header_h = team_col_h + 12

        row_heights: List[int] = []
        for group in normalized_groups:
            team_count = max(1, len(group))
            h = team_count * cell_h
            row_heights.append(h)
        row_group_gap = max(0, int(row_group_gap))
        grid_h = sum(row_heights) + row_group_gap * max(0, len(row_heights) - 1)

        canvas_w = margin + left_panel_w + n_cols * cell_w + margin
        canvas_h = margin + title_h + title_gap + header_h + 8 + grid_h + margin

        im = self._new_jjc_canvas(canvas_w, canvas_h, colors)
        draw = ImageDraw.Draw(im)

        title_font = ImageFont.truetype(self.font_path, 30)
        cell_font = ImageFont.truetype(self.font_path, 24)

        # Title
        if has_title:
            draw.text((margin, margin), title.strip(), fill=colors["font"], font=title_font)

        header_y0 = margin + title_h + title_gap
        grid_x0 = margin + left_panel_w
        grid_y0 = header_y0 + header_h + 8

        # Top areas
        draw.rectangle(
            [margin, header_y0, grid_x0, grid_y0],
            fill=colors["header_bg"],
            outline=colors["rowline"],
            width=1,
        )
        draw.rectangle(
            [grid_x0, header_y0, grid_x0 + n_cols * cell_w, grid_y0],
            fill=colors["header_bg"],
            outline=colors["rowline"],
            width=1,
        )

        # Left area background
        draw.rectangle(
            [margin, grid_y0, grid_x0, grid_y0 + grid_h],
            fill=colors["even_row_cell_bg"],
            outline=colors["rowline"],
            width=1,
        )

        header_obj = header_result or SimpleNamespace(
            player_info=None,
            talent_level=None,
            talent_skill=None,
            team_skill=None,
        )
        info_lines = self._header_info_lines(header_obj)
        print(info_lines)
        info_pad_x = 12
        info_pad_y = 8
        info_x = margin + info_pad_x
        info_y = header_y0 + info_pad_y
        info_w = max(30, left_panel_w - info_pad_x * 2)
        info_h = max(30, (grid_y0 - header_y0) - info_pad_y * 2)

        fit_font = ImageFont.truetype(self.font_path, 14)
        fit_line_h = 20
        for font_size in range(24, 11, -1):
            test_font = ImageFont.truetype(self.font_path, font_size)
            line_h = max(font_size + 6, int(font_size * 1.35))
            total_h = line_h * len(info_lines)
            max_w = max((test_font.getbbox(line)[2] - test_font.getbbox(line)[0]) for line in info_lines)
            if total_h <= info_h and max_w <= info_w:
                fit_font = test_font
                fit_line_h = line_h
                break

        info_start_y = info_y + max(0, (info_h - fit_line_h * len(info_lines)) // 2)
        await self._draw_header_info(
            draw,
            fit_font,
            header_obj,
            info_x,
            info_start_y,
            line_height=fit_line_h,
            align="left",
        )

        # Defend teams on top (vertical icons per column, same icon size as attacks)
        for col, raw_units in enumerate(defend_units):
            x = grid_x0 + col * cell_w
            draw.rectangle(
                [x, header_y0, x + cell_w, grid_y0],
                fill=colors["header_bg"],
                outline=colors["colline"],
                width=1,
            )
            icon_x = x + (cell_w - icon_size) // 2
            base_y = header_y0 + 6
            units = self._normalize_units(raw_units)
            for i, unit in enumerate(reversed(units)):
                icon_y = base_y + i * (icon_size + icon_gap)
                await self._draw_unit_at(
                    draw,
                    im,
                    unit,
                    icon_x,
                    icon_y,
                    icon_size=icon_size,
                    ex_size=0,
                )

        # Attack groups on left + matrix cells (group -> subrows)
        group_y = grid_y0
        for g_idx, (raw_group, group_rows) in enumerate(zip(normalized_groups, normalized_matrices)):
            group_h = row_heights[g_idx]
            group_bg = colors["odd_row_cell_bg"] if g_idx % 2 == 0 else colors["even_row_cell_bg"]
            draw.rectangle(
                [margin, group_y, grid_x0 + n_cols * cell_w, group_y + group_h],
                fill=group_bg,
                outline=colors["rowline"],
                width=1,
            )

            if label_panel_w > 0:
                draw.line(
                    [(margin + label_panel_w, group_y), (margin + label_panel_w, group_y + group_h)],
                    fill=colors["rowline"],
                    width=1,
                )
                label = normalized_labels[g_idx] if g_idx < len(normalized_labels) else ""
                if label:
                    lines = [line for line in label.splitlines() if line.strip()]
                    if not lines:
                        lines = [label]
                    line_gap = 4
                    line_sizes = [label_font.getbbox(line) for line in lines]
                    line_heights = [(b - t) for l, t, r, b in line_sizes]
                    total_h = sum(line_heights) + line_gap * max(0, len(lines) - 1)
                    y = group_y + (group_h - total_h) / 2
                    for line, (l, t, r, b) in zip(lines, line_sizes):
                        line_w = r - l
                        line_h = b - t
                        x = margin + (label_panel_w - line_w) / 2
                        draw.text((x, y - t), line, fill=colors["font"], font=label_font)
                        y += line_h + line_gap

            team_start_x = margin + label_panel_w + (team_panel_w - team_w) // 2
            for r_idx, (raw_units, row_cells) in enumerate(zip(raw_group, group_rows)):
                row_y = group_y + r_idx * cell_h

                draw.rectangle(
                    [margin + label_panel_w, row_y, grid_x0, row_y + cell_h],
                    fill=group_bg,
                    outline=colors["rowline"],
                    width=1,
                )

                units = self._normalize_units(raw_units)
                await self._draw_unit_row(
                    draw,
                    im,
                    units,
                    row_y + max(0, (cell_h - icon_size) // 2),
                    align_right=False,
                    margin=team_start_x,
                    icon_size=icon_size,
                    unit_gap=icon_gap,
                    ex_size=0,
                )

                for col in range(n_cols):
                    x = grid_x0 + col * cell_w
                    rate = row_cells[col]
                    if rate == -1:
                        fill = "#D4D8DE"
                        text = "N/A"
                        text_color = "#72777E"
                    else:
                        if rate >= 0.8:
                            fill = "#95E0B7"
                        elif rate >= 0.5:
                            fill = "#F5E184"
                        else:
                            fill = "#F4AAB0"
                        text = f"{rate:.0%}"
                        text_color = "#1E1E1E"

                    draw.rectangle(
                        [x, row_y, x + cell_w, row_y + cell_h],
                        fill=fill,
                        outline=colors["rowline"],
                        width=1,
                    )

                    l, t, r, b = cell_font.getbbox(text)
                    tx = x + (cell_w - (r - l)) / 2
                    ty = row_y + (cell_h - (b - t)) / 2 - t
                    draw.text((tx, ty), text, fill=text_color, font=cell_font)

            group_y += group_h + row_group_gap

        # Grid border
        draw.rectangle(
            [grid_x0, grid_y0, grid_x0 + n_cols * cell_w, grid_y0 + grid_h],
            outline=colors["rowline"],
            width=1,
        )

        self._draw_jjc_frame(draw, im, colors)
        return im

    async def draw_jjc_blind_matrix(
        self,
        result: 'JJCMatrixResult'
    ) -> Image.Image:
        attack_groups = [[team] for team in result.attacks]
        group_matrices = [[rate] for rate in result.matrix]
        return await self._draw_blind_matrix_common(
            attack_groups=attack_groups,
            group_matrices=group_matrices,
            defend_units=result.defends,
            header_result=result.header_result,
        )

    async def draw_pjjc_blind_matrix(
        self,
        result: 'PJJCMatrixResult'
    ) -> Image.Image:
        group_left_labels = [
            f"{round_cnt}局{need_wins}胜率:\n{max(0.0, min(1.0, float(rate))) * 100:.1f}%"
            for id, rate in enumerate(result.win_rate) for round_cnt in [len(result.attacks[id])] for need_wins in [(round_cnt // 2 + 1)]
        ]
        return await self._draw_blind_matrix_common(
            attack_groups=result.attacks,
            group_matrices=result.matrix,
            defend_units=result.defends,
            header_result=result.header_result,
            row_group_gap=16,
            group_left_labels=group_left_labels,
        )

instance = Drawer()

