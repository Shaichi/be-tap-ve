# Giao sơ đồ qua draw.io MCP

Repo chính thức: `jgraph/drawio-mcp`, gồm 2 dạng server. Kiểm tra tool nào đang có trong phiên
(tên tool có thể có tiền tố `mcp__<server>__`).

## 1. Tool Server – gói npm `@drawio/mcp`

Cài cho Claude Code:
```bash
claude mcp add drawio -- npx -y @drawio/mcp
```
(Claude Desktop: thêm vào `mcpServers` trong config `{"command": "npx", "args": ["-y", "@drawio/mcp"]}`.)

Google Antigravity (IDE/CLI): thêm vào `~/.gemini/config/mcp_config.json` (bản cũ: `~/.gemini/antigravity/mcp_config.json`;
hoặc theo workspace: `.agents/mcp_config.json`), rồi *Manage MCP Servers › Refresh*:
```json
{ "mcpServers": { "drawio": { "command": "npx", "args": ["-y", "@drawio/mcp"] } } }
```
Trên Windows nếu không chạy được, dùng đường dẫn tuyệt đối tới `npx.cmd` trong `command`.

Đã kiểm chứng với `@drawio/mcp` 1.6 (server `drawio-mcp`), 7 tool:

| Tool | Tham số | Dùng thế nào |
|---|---|---|
| `open_drawio_xml` | `content`, `lightbox`, `dark`, `postLayout` | **Cách chính.** Sinh file bằng `uml2drawio.py -o x.drawio`, đọc toàn bộ nội dung file và truyền vào `content` (nhận cả `<mxfile>` nhiều trang). Trả về URL `https://app.diagrams.net/...#create=...` (dữ liệu nén nằm sau `#`). **Không truyền `postLayout`.** |
| `list_pages` | `path` | Liệt kê trang trong file `.drawio` cục bộ – dùng để xác nhận file đã sinh. |
| `get_page` | `path`, `page` | Lấy `<mxGraphModel>` của một trang (tự giải nén) – dùng để kiểm tra/sửa sơ đồ người dùng đưa (chạy `validate_drawio.py` trên kết quả). |
| `set_page` | `path`, `page`, `content` | Thay nội dung một trang trong file cục bộ, giữ nguyên các trang khác. Dùng để cập nhật 1 sơ đồ trong file nhiều trang: `uml2drawio.py spec.json --xml-only` → `set_page`. |
| `search_shapes` | `query`, `limit` | Chỉ cần cho icon đặc biệt (AWS, mạng...) trong deployment diagram. |
| `open_drawio_csv` | – | Không dùng – CSV import dùng auto-layout, mất ký hiệu UML, có thể chồng hình. |
| `open_drawio_mermaid` | – | Không dùng cho COMET – Mermaid không có stereotype COMET, layout không kiểm soát. |

`lightbox` / `dark`: để mặc định trừ khi người dùng yêu cầu.

Kiểm tra server khi phiên chưa nạp tool MCP (tool chỉ xuất hiện ở phiên mở sau khi cài):
```bash
python scripts/mcp_smoke.py --list
python scripts/mcp_smoke.py - --tool list_pages --args '{"path": "/abs/path/x.drawio"}'
```

## 2. MCP App Server (render sơ đồ inline trong chat)

| Tool | Dùng thế nào |
|---|---|
| `create_diagram` | Truyền XML **một trang**: `python scripts/uml2drawio.py spec.json --xml-only` → chuỗi `<mxGraphModel>`. **Không** bật `postLayout` / ELK / bất kỳ auto-layout nào: bố cục đã được tối ưu và kiểm tra; layout lại sẽ làm lệch nhãn multiplicity, route đường xuyên hình, phá thứ tự cột COMET. Nhiều sơ đồ → gọi nhiều lần, mỗi spec một lần. |
| `search_shapes` | Chỉ cần khi người dùng muốn icon đặc biệt (AWS, mạng...) trong deployment diagram. Hình UML chuẩn đã có sẵn trong style. |

## 3. Khi không có MCP draw.io

- Giao file `.drawio` – mở bằng draw.io Desktop, VS Code extension "Draw.io Integration", hoặc
  app.diagrams.net (File › Open from › Device).
- Xem nhanh offline: `python scripts/preview_svg.py x.drawio -o x.html` (bản xem gần đúng, không thay
  cho draw.io).
- Không tự ý tạo URL chia sẻ/viewer công khai chứa nội dung sơ đồ khi người dùng chưa đồng ý (nội dung
  sẽ bị gửi ra dịch vụ bên ngoài).

## 4. Sửa XML an toàn (khi buộc phải sửa tay hoặc sửa file của người dùng)

Cấu trúc tối thiểu:
```xml
<mxGraphModel><root>
  <mxCell id="0"/>
  <mxCell id="1" parent="0"/>
  <mxCell id="v1" value="..." style="..." vertex="1" parent="1">
    <mxGeometry x="40" y="40" width="120" height="60" as="geometry"/>
  </mxCell>
  <mxCell id="e1" style="edgeStyle=orthogonalEdgeStyle;endArrow=open;endFill=0;" edge="1" parent="1" source="v1" target="v2">
    <mxGeometry relative="1" as="geometry"><Array as="points"><mxPoint x="100" y="160"/></Array></mxGeometry>
  </mxCell>
</root></mxGraphModel>
```
Quy tắc:
- `id` duy nhất; `source`/`target`/`parent` phải trỏ tới id tồn tại.
- Toạ độ của phần tử con (`parent` = container) là **tương đối** với container.
- Nhãn trên đường: cell con `vertex="1" connectable="0" parent="<edge id>"`, style `edgeLabel;...`,
  geometry `relative="1"` với `x` ∈ [-1, 1] (vị trí dọc đường) và `<mxPoint as="offset">`.
- Cố định điểm nối: `exitX/exitY/exitPerimeter=0`, `entryX/entryY/entryPerimeter=0` – đổi vị trí hình
  mà không cập nhật các giá trị này sẽ khiến đường đi xuyên hình.
- Giá trị HTML (`html=1`) phải escape: `&lt;`, `&gt;`, `&amp;`, `&quot;`; xuống dòng dùng `<br>`
  (đã escape thành `&lt;br&gt;` trong thuộc tính).
- Stereotype: «» (U+00AB/U+00BB), không dùng `&lt;&lt;`.
- Sau khi sửa: `python scripts/validate_drawio.py file.drawio` phải 0 ERROR.

Khuyến nghị: thay vì sửa tay, dựng lại spec từ sơ đồ và sinh lại – nhanh hơn và luôn sạch lỗi.
