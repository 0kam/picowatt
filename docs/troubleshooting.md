# トラブルシューティング

症状から原因へ引けるように並べてある。配線図は
[hardware/README.md](../hardware/README.md#使い方配線図) を参照。

## 症状早見表

| 症状 | まず疑うこと |
|---|---|
| VBUS が 0 V と −数十 V の間を 50/60 Hz で振動する | **電源の − が J5 (GND) に来ていない** |
| VBUS が 0 V 付近で動かない、電流は出ている | INA228 裏の **VBus ジャンパが開いている** |
| 電流の符号が逆（負の電流） | VIN+ と VIN− が逆 |
| ch1 が `channels 0x01` で見えない | ch1 の A0 ジャンパが開いている（0x40 が 2 枚） |
| `frame gaps` / `ring drops` が 0 でない | USB 帯域超過。プリセットを落とす |

## VBUS が 0 V と −数十 V の間で振動する（GND リンク忘れ）

**症状**: 電源を入れても VBUS が安定せず、0 V と −50 V 前後の間を商用電源の
周波数（東日本 50 Hz / 西日本 60 Hz）で往復する。電流値はそれらしく見える
ことが多い。`picowatt-cli` は次を出す。

```
       vbus -26.1234 V (sd 18.7, min -53.1, max 0.2)  current 120.0 mA (sd 0.4)
       WARNING: ch0 bus voltage goes negative (min -53.1 V) - the supply '-' is
       probably not connected to the GND terminal (J5), or the VBus jumper is
       open. See docs/troubleshooting.md
```

**原因**: INA228 の A/D は VBUS を **自分の GND ピン基準**で測る。GND ピンは
キャリア基板の GND ベタ（＝Pico の GND）に繋がっているだけで、測定対象の
電源系とは **J5 を通してしか繋がらない**。電源の − を J5 に落とし忘れると
基板全体が電源系から浮き、浮いた導体が商用電源のハムを拾って、実在しない
電圧が表示される。

![VBUS は INA228 の GND ピン基準](../hardware/docs/vbus-reference.svg)

よくある形は「電源の − を測定対象の − に直結して、J5 には何も繋がない」。
線としては閉じているので気付きにくい。

![GND リンクを忘れた配線](../hardware/docs/wiring-floating-gnd.svg)

**対処**: 安定化電源の − から J5 の空いている口へ線を 1 本足す。これだけで
直る。この線には測定電流はほぼ流れない（電位を決めるだけ）ので細くてよい。

**注意**: GND の共通接続は **1 点だけ**にする。電源の − と測定対象の − の
両方を J5 に落とすのは正しい（J5 の 2 口は基板内で繋がっており、それが
1 点）。それとは別に PC の USB GND などを経由して 2 か所目ができるとループに
なる。

## VBUS が 0 V のまま動かない（VBus ジャンパ開放）

**症状**: 電流は正しく出るが VBUS だけ 0 V 付近で動かない、または微小な
ハムだけ乗る。

**原因**: Adafruit INA228 の VBUS ピンはデフォルトで VIN+ から切り離されて
いる。裏面の **VBus ジャンパ**を閉じないとバス電圧を測る配線が無い。

**対処**: INA228 ×2 とも裏の VBus ジャンパをはんだで閉じる（ハイサイド構成）。

## 電流が負になる

VIN+ と VIN− が逆。電源（または DC-DC 出力）の ＋ を **VIN+** に、負荷側を
**VIN−** に繋ぐ。ネジ端子台の真ん中（VBus）には何も繋がない。

## ch1 が見えない

接続時のログが `channels 0x01` なら ch1 が応答していない。ch1 に挿した
INA228 の裏の **A0 ジャンパ**が閉じているか確認する（閉で 0x41）。開いた
ままだと 0x40 が 2 枚になり、ch1 は存在しない扱いになる。

## frame gaps / ring drops が出る

`picowatt-cli` の末尾に出る `frame gaps` はホスト側の取りこぼし、`device
ring drops` は Pico 側のリングバッファ溢れ。どちらも 0 が正常。出る場合は
`--preset` を遅いものにするか、USB ハブを介さず直結する。プリセット一覧は
[protocol.md](protocol.md)。
