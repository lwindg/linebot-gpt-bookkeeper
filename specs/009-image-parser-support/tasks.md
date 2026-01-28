# 009 圖片 Parser 模式支援 - 任務清單

## Phase 1: Image Envelope

- [x] T001 定義 ImageAuthoritativeEnvelope 資料結構（app/pipeline/image_flow.py）
- [x] T002 新增 image_handler 轉換函式：Vision 回應 → ImageAuthoritativeEnvelope（app/services/image_handler.py）
- [x] T003 新增單元測試：Image envelope 轉換（tests/unit/test_image_envelope.py）

## Phase 2: 批次 Enrichment

- [x] T004 新增批次 enrichment 模組（app/enricher/receipt_batch.py）
- [ ] T005 更新 enrichment schema：支援 receipt items 批次格式（app/schemas.py）
- [x] T006 新增單元測試：批次 enrichment mapping（tests/unit/test_receipt_batch.py）

## Phase 3: 外幣換算

- [x] T007 加入外幣換算流程（app/pipeline/image_flow.py）
- [x] T008 新增單元測試：外幣收據換算（tests/unit/test_receipt_fx.py）

## Phase 4: Pipeline 整合

- [x] T009 建立圖片 pipeline 主流程（app/pipeline/image_flow.py）
- [x] T010 在 pipeline/router.py/line_handler 加入圖片分支（圖片入口由 line_handler 直接呼叫 image_flow）
- [x] T011 更新 line_handler：圖片訊息改走 pipeline（app/line_handler.py）

## Phase 5: Converter + Validator

- [x] T012 擴充 validator 支援 image items（app/enricher/validator.py）
- [x] T013 擴充 converter：ImageAuthoritativeEnvelope → MultiExpenseResult（app/converter.py）

## Phase 6: 功能測試

- [x] T014 新增圖片 functional suite（tests/functional/suites/image_receipt.jsonl）
- [x] T015 新增圖片整合測試（tests/integration/test_receipt_pipeline.py）

## Phase 7: 文件更新

- [x] T016 更新圖片測試與使用說明（docs/LOCAL_VISION_TEST.md）
