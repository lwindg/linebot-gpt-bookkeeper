# v1.2.0: Vision API Foundation

> GPT-4 Vision API integration for receipt image recognition

**Release Date**: 2025-11-15

---

## ✨ What's New

### 📸 Receipt Image Recognition

Upload receipt photos directly to LINE bot for automatic transaction extraction.

**Supported Receipt Types**:
- Paper receipts with printed text
- Digital receipts (screenshots)
- Restaurant bills
- Store receipts

**Extracted Information**:
- Items and prices
- Payment method
- Merchant name
- Date and time
- Category classification

### 🔧 Image Processing

- Automatic image compression (max 800px width)
- JPEG quality optimization (85%)
- Smart format handling (bytes/stream)
- Base64 encoding for API transmission

---

## 📝 Usage Example

1. Take a photo of your receipt
2. Send the image to LINE bot
3. Bot automatically extracts and confirms transaction details
4. Webhook sent to Make.com for data storage

```
User: [Uploads receipt image]
Bot:
✅ 記帳成功！已從收據識別：

📋 #1 拿鐵咖啡
💰 120 元

📋 #2 蛋糕
💰 85 元

💳 付款方式：信用卡
📋 商家：星巴克
🔖 交易ID：20251115-150000
```

---

## 🔄 Breaking Changes

None - maintains full backward compatibility with v1.0.

---

## 🐛 Bug Fixes

- Fixed classification consistency for meal categories
- Improved payment method recognition
- Enhanced error handling for image processing

---

## 📦 Technical Details

**New Modules**:
- `app/image_handler.py` - Image download and processing
- Image compression using Pillow

**Dependencies Added**:
- `Pillow` for image processing

**Modified Files**:
- `app/line_handler.py` - Added image message handling
- `app/gpt_processor.py` - Added Vision API integration
- `app/prompts.py` - Added VISION_PROMPT

---

## 🚀 Deployment

### Prerequisites
- OpenAI API key with GPT-4 Vision access
- LINE Bot SDK 3.8.0+
- Python 3.11+

### Environment Variables
```bash
OPENAI_API_KEY=sk-...              # Required: Vision API access
LINE_CHANNEL_ACCESS_TOKEN=...      # Existing
LINE_CHANNEL_SECRET=...            # Existing
MAKE_WEBHOOK_URL=...               # Existing
```

### Installation
```bash
pip install -r requirements.txt
```

No database migration required.

---

## 📊 Known Limitations

1. **Receipt Quality**: Requires clear, readable photos
   - Blurry or low-light images may fail
   - Handwritten receipts less reliable

2. **Language**: Optimized for Traditional Chinese receipts
   - English receipts supported but may need tuning

3. **Currency**: Only TWD (Taiwan Dollar) supported

---

## 🔮 Coming Next

- **v1.3.0**: Enhanced classification and error handling
- **v1.5.0**: Multi-item expense processing
- **v1.7.0**: Advance payment tracking

---

## 📚 Documentation

- Full Release Notes: [`RELEASE_NOTES_v1.2.0.md`](./RELEASE_NOTES_v1.2.0.md)
- Technical Spec: `specs/001-linebot-gpt-bookkeeper/`

---

**Commit**: `35b19ff`
**Contributors**: Claude AI, Spec Kit Framework
