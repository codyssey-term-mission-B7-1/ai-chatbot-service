#!/usr/bin/env node
/**
 * 프론트 JS 난독화 빌드 (CI/CD 전용, ADR-009 · docs/OBFUSCATION.md)
 *
 * 사용법:
 *   node obfuscate.mjs --in <입력디렉터리> [--out <출력디렉터리>]
 *   --out 생략 → in-place 덮어쓰기 (CD 배포 빌드용)
 *
 * 원칙:
 *   - 저장소 소스는 가독 유지(MIT 공개 정책) — 난독화 대상은 "배포 산출물"만이다.
 *   - seed 고정(20260912)으로 동일 소스 → 동일 산출물(재현 가능한 빌드, 증빙 culture).
 *   - renameGlobals=false가 필수 전제: FormUtils 같은 파일 간 전역 계약이
 *     form-utils.js → auth.js·chat.js·password-reset.js 로 참조된다.
 */
import obfuscatorPkg from 'javascript-obfuscator';
import { mkdir, readdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

// CommonJS 모듈 — named export가 없으므로 default에서 역참조
const { obfuscate } = obfuscatorPkg;

const SEED = 20260912;

const OPTIONS = {
  // 기본 난독화
  compact: true,                      // 한 줄 압축 + 주석 제거
  simplify: true,
  identifierNamesGenerator: 'hexadecimal', // 식별자 0x... 계열
  numbersToExpressions: true,         // 숫자를 표현식으로 변환
  // 구조 난독화 (중간 강도 — UI 스크립트 특성상 과한 bloat은 피한다)
  controlFlowFlattening: true,
  controlFlowFlatteningThreshold: 0.5,
  stringArray: true,                  // 문자열을 base64 배열로 이동
  stringArrayEncoding: ['base64'],
  stringArrayThreshold: 0.9,
  stringArrayRotate: true,
  stringArrayShuffle: true,
  stringArrayCallsTransform: true,
  stringArrayCallsTransformThreshold: 0.5,
  splitStrings: true,
  splitStringsChunkLength: 8,
  unicodeEscapeSequence: true,        // 한글 문자열을 \uXXXX로 — 텍스트 힌트 제거
  // 비활성 (의도)
  deadCodeInjection: false,           // bloat·미묘한 동작 변화 위험
  debugProtection: false,             // devtools 무한루프 — 데모 서비스 특성상 비활성
  selfDefending: false,               // beautify 감지 예외 — 호환성 유지
  disableConsoleOutput: false,        // console 동작 유지(의도 변경 최소화)
  transformObjectKeys: false,         // 객체 키 표현 변환은 프로퍼티 계약(FormUtils.*) 유지 전제
  renameGlobals: false,               // ★ 필수: FormUtils 등 전역 계약 보존
  seed: SEED,                         // 결정적 빌드
};

async function main() {
  const args = process.argv.slice(2);
  let input = 'static/js';
  let output = null;
  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === '--in') input = args[++i];
    else if (arg === '--out') output = args[++i];
    else if (arg.startsWith('in=')) input = arg.slice(3);
    else if (arg.startsWith('out=')) output = arg.slice(4);
    else throw new Error(`알 수 없는 인자: ${arg} (사용법: --in <dir> [--out <dir>])`);
  }
  if (!input) throw new Error('--in 지정 필요');

  const files = (await readdir(input)).filter((f) => f.endsWith('.js')).sort();
  if (files.length === 0) throw new Error(`${input}에 .js 파일이 없습니다`);
  if (output) await mkdir(output, { recursive: true });

  for (const f of files) {
    const source = await readFile(path.join(input, f), 'utf8');
    const result = obfuscate(source, OPTIONS).getObfuscatedCode();
    const dest = path.join(output ?? input, f);
    await writeFile(dest, result, 'utf8');
    console.log(`  ✅ ${f}: ${source.length} → ${result.length} bytes`);
  }
  console.log(`난독화 완료 — ${files.length}개 파일 (seed=${SEED}, 결정적 빌드)`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
