# picowatt

Raspberry Pi Pico 2 + INA228 による PPK2 ライクな消費電力測定システム。

## クイックスタート

### リリース版を使う(推奨)

1. **ファームウェア**: [Releases](https://github.com/0kam/picowatt/releases) から
   `picowatt-vX.Y.Z.uf2` をダウンロードし、BOOTSEL ボタンを押しながら Pico 2 を
   USB 接続して現れる `RP2350` ドライブにドラッグ(または
   `picotool load -fx picowatt-vX.Y.Z.uf2`)。
2. **PC アプリ**: [uv](https://docs.astral.sh/uv/) があれば1行で起動できる:

   ```sh
   uvx picowatt        # GUI
   uvx --from picowatt picowatt-cli --seconds 10 --csv out.csv
   ```

   (pip 派は `pipx install picowatt` でも可)

### ソースからのビルドと書き込み

必要なもの: cmake、ARM GNU toolchain、[pico-sdk](https://github.com/raspberrypi/pico-sdk) 2.3+(`lib/tinyusb` サブモジュール込み)、picotool 2.3+。

```sh
export PICO_SDK_PATH=~/pico-sdk            # 既定値
export PICO_TOOLCHAIN_PATH=~/toolchains/arm-gnu-toolchain-...  # PATH に無い場合
./firmware/build.sh                        # → firmware/build/picowatt.uf2

# 初回のみ BOOTSEL ボタンを押しながら USB 接続して:
picotool load -fx firmware/build/picowatt.uf2
# 2回目以降はボタン不要(実行中ファームがリブートコマンドを受け付ける)
```

UF2 ドライブへのドラッグ&ドロップでも書き込めるが、USB マスストレージが
制限された環境では picotool 経由(PICOBOOT)が使える。

### PC アプリ

```sh
cd app
uv sync
uv run picowatt        # GUI
uv run picowatt-cli --seconds 10 --csv out.csv   # ヘッドレスキャプチャ
```

GUI: Connect → Start でストリーミング開始。Measure チェックで電力プロット上の
任意区間を選択して Wh/Ah を積算。Log CSV… で全サンプルをファイルに記録。
Calibrate… でゼロ校正・1点ゲイン校正(ボードIDごとに自動保存され、接続時に
自動適用)。プロトコル仕様は [docs/protocol.md](docs/protocol.md)、実測性能は
[docs/verification.md](docs/verification.md) を参照。値がおかしいときは
[docs/troubleshooting.md](docs/troubleshooting.md)（症状から引ける）。

## 概要

INA228 電力モニタを Pico 2 で読み取り、USB シリアル経由で PC に転送。PC 側アプリでリアルタイム表示・ロギング・任意区間の電力量(Wh)積算を行う。

対応する測定モード:

- **消費電力測定** — 機器の消費電力を INA228 1枚で測定
- **DC-DC 効率測定** — INA228 2枚で入出力を同時測定し、効率を算出

## ハードウェア構成

| 役割 | 型番 | 備考 |
|---|---|---|
| MCU | Raspberry Pi Pico 2 (RP2350) | USB CDC で PC 接続 |
| 電力モニタ | Adafruit INA228 ×2 | 15mΩ 0.1% シャント搭載、20bit ADC |
| ディスプレイ | SSD1306 128×64 I2C OLED | 秋月 |
| 電源 | アズワン PS30V5A10 | 0-30V / 0-5A |
| 電子負荷 | ET5410A+ | 効率測定時の負荷掃引用 |

### I2C アドレス

| デバイス | アドレス | 設定 |
|---|---|---|
| SSD1306 OLED | `0x3C` | — |
| INA228 #1 (入力側) | `0x40` | デフォルト |
| INA228 #2 (出力側) | `0x41` | 基板裏 A0 ジャンパを閉 |

### 結線

ロジック側は I2C0 バスに全デバイスをぶら下げる。ブレッドボード配線の代わりに
キャリア基板を起こす場合は [hardware/](hardware/README.md) を参照(KiCad プロジェクト)。

| Pico 2 | 接続先 |
|---|---|
| 3V3 OUT (pin 36) | INA228 ×2 VIN / OLED VCC |
| GND (pin 38) | INA228 ×2 GND / OLED GND / 電源 − (1点のみ) |
| GP4 (pin 6) SDA | INA228 ×2 SDA / OLED SDA |
| GP5 (pin 7) SCL | INA228 ×2 SCL / OLED SCL |

I2C プルアップは INA228 基板の 10kΩ が効くため追加不要。

電力ラインはハイサイド測定。**基板裏の VBus ジャンパを閉じる**(VBUS が VIN+ に接続され、ハイサイド構成になる)。

```
電源(+) → #1 VIN+ ─[15mΩ]─ #1 VIN− → DUT(+)
電源(−) ←──────────────────────────── DUT(−)
```

効率測定時は出力側に #2 を追加:

```
DUT出力(+) → #2 VIN+ ─[15mΩ]─ #2 VIN− → 電子負荷(+)
DUT出力(−) ←───────────────────────────── 電子負荷(−)
```

**電源の − は必ず picowatt の GND（キャリア基板なら J5）に繋ぐ。** INA228 は
バス電圧を自分の GND ピン基準で測るので、この 1 本が無いと基板が電源系から
浮き、VBUS が 0 V と −数十 V の間を 50/60 Hz で振動する（実在しない電圧）。
`picowatt-cli` はこの状態を検出して `WARNING: bus voltage goes negative` を
出す。図解は [docs/troubleshooting.md](docs/troubleshooting.md)。

![GND リンクを忘れるとこうなる](hardware/docs/wiring-floating-gnd.svg)

GND の共通接続は 1 点のみ。複数箇所で接続するとループになる。

## キャリブレーション

INA228 は `SHUNT_CAL` レジスタ (0x02) にシャント値とフルスケールから決まる係数を書き込む必要がある。

```
CURRENT_LSB = 最大期待電流 / 2^19
SHUNT_CAL   = 13107.2e6 × CURRENT_LSB × R_SHUNT
```

`R_SHUNT = 0.015` (Adafruit ボード搭載値)。

デフォルト設定 (3A 想定, ADCRANGE=0 / ±163.84mV):

```
CURRENT_LSB = 8e-6        # 8 µA/LSB, フルスケール約 4.19A
SHUNT_CAL   = 1573
```

低電流モード (ADCRANGE=1 / ±40.96mV) では CURRENT_LSB を 1/4 に下げて分解能を上げる。
ADCRANGE=1 では **SHUNT_CAL の計算値を 4 倍**する必要があるが、LSB の 1/4 と相殺して
レジスタ値は同じになる:

```
CURRENT_LSB = 2e-6        # 2 µA/LSB, フルスケール約 1.05A
SHUNT_CAL   = 1573        # = 4 × 13107.2e6 × 2e-6 × 0.015
```

出荷時のシャント実値は公称から数%ずれることがあるため、既知電流での 1 点校正を推奨。

## 機能要件

### ファームウェア (Pico 2)

- INA228 ×2 の初期化・設定変更 (ADCRANGE, 変換時間, 平均化回数)
- 定期サンプリングと USB シリアルへのストリーミング
- OLED へのリアルタイム数値表示
- PC からのコマンド受信 (レンジ切替、サンプリングレート変更、ゼロ校正、モード切替)
- I2C は 400kHz 以上 (Pico 2 は 1MHz まで可)

### PC アプリ

- シリアル接続とリアルタイムグラフ表示 (電圧 / 電流 / 電力)
- CSV ロギング
- **表示中の任意範囲を選択して電力量(Wh)を積算**
- 効率モード時は入出力電力と効率(%)を同時表示
- 測定設定の変更 UI

## 想定サンプリングレート

I2C 経由のため PPK2 (100kSa/s) 相当は狙わない。数百 Hz〜数 kHz を目標。変換時間と平均化回数の設定でノイズと速度をトレードオフする。

## 参考

- [Adafruit INA228 Learn Guide](https://learn.adafruit.com/adafruit-ina228-i2c-power-monitor)
- INA228 データシート (TI)

## ライセンス

GPL-3.0 — 詳細は [LICENSE](LICENSE) を参照。
