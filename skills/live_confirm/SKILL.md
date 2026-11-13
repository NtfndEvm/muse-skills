# Live Confirm

Tujuanmu adalah memeriksa harga live sebelum entry dan saat memantau posisi, supaya gerakan yang terjadi di dalam candle 15m tidak terlewat. Candle 15m yang sudah tutup tetap menjadi satu-satunya sumber konfirmasi, dan skill ini hanya menambah bacaan cepat di antaranya.

## Periksa harga live sebelum memutuskan

- Jalankan live check dari folder `scripts` di dalam folder skill ini dan ganti simbol serta level dengan yang sedang dipantau.

```bash
python3 live_check.py --symbol MAGMA --level 0.2807
```

- Baca harga live dan jam WIB dari hasil perintah itu dan cantumkan keduanya di setiap jawaban yang memakai hasil live check.

- Perlakukan candle 5m yang masih berjalan sebagai data yang dibuang dari analisis, dan laporkan harga live di dalamnya hanya sebagai harga berjalan, bukan sebagai konfirmasi.

- Laporkan penembusan level yang hanya terlihat di harga live sebagai belum terkonfirmasi, dan jangan pernah menyebutnya breakout atau bounce terkonfirmasi sebelum candle yang relevan tutup di atas level itu.

- Minta konfirmasi akhir dari `candle-reader-15m` sebelum entry, karena live confirm tidak menggantikan pembacaan candle tutup.

- Baca kode keluar perintah itu. Kode 0 berarti ketiga bacaan terbaca, dan kode 2 berarti ada yang gagal. Baris terakhir menyebut bagian yang gagal, sedangkan dua bagian lain tetap bisa dipakai.

- Tambahkan `--format json` bila hasil perlu dibaca mesin, karena perintah itu mengeluarkan satu JSON gabungan berisi simbol, pair, level, status, dan ketiga bacaan.

## Baca tiga sinyal bersama

- Baca momentum 5m dari `reader_5m` dan kenali sinyal kuat serta sinyal lemahnya. Sinyal kuat adalah higher high dibanding 3 candle sebelumnya, volume tinggi, breakout terkonfirmasi atau retest bertahan, dan candle bullish yang tutup dekat high. Sinyal lemah adalah sumbu atas 0,4 atau lebih, volume rendah, penolakan sumbu, support jebol, atau candle bearish besar.

- Petakan hasil 5m menjadi DITERUSKAN bila ada higher high tanpa sinyal lemah, MELEMAH bila sinyal lemah ada dan jumlahnya sama atau lebih banyak dari sinyal kuat, dan NETRAL bila tidak ada tanda jelas.

- Baca order book dari `orderbook`. Ukur total bid dan ask dalam jarak 1 persen dari harga tengah dan baca imbalance di atas 0,6 sebagai bid dominan dan di bawah 0,4 sebagai ask dominan. Periksa level yang dipantau dalam jarak 0,3 persen pada sisi yang relevan dan sebut TEBAL bila kedalamannya mencapai acuan, dan TIPIS bila di bawah acuan.

- Sebut level yang berada di luar jangkauan 50 level order book sebagai TIDAK TERUKUR, bukan TIPIS, dan tambahkan peringatan bahwa kedalamannya tidak terukur.

- Baca agresi dari `delta`. Hitung delta dari 100 trade terakhir dan sebut dominan bila nilai absolutnya 10 persen atau lebih, dan seimbang bila di bawah itu. Tambahkan peringatan bila sampelnya kurang dari 20 trade.

- Gabungkan ketiga sinyal sebelum menyimpulkan. Kesepakatan ketiganya menguatkan bacaan, sedangkan pertentangan antar sinyal berarti hasilnya belum jelas dan entry menunggu konfirmasi candle tutup.

## Laporkan sentuhan level tanpa menunggu

- Laporkan sentuhan atau penembusan level segera setelah live check menampilkannya, dan beri label belum terkonfirmasi bila candle belum tutup.

- Sertakan harga live, level yang tersentuh, jam WIB, dan sinyal mana dari ketiganya yang sependapat.

- Pasang level pantau yang sudah muncul di analisis ke pemantauan langsung tanpa bertanya lagi kepada user, karena user sudah meminta hal itu.

- Tutup laporan dengan satu kalimat tentang apa yang masih ditunggu, yaitu candle tutup berikutnya atau konfirmasi dari `candle-reader-15m`.

## Batasan dan yang belum teruji

- Gunakan hanya endpoint publik Bitget v2 tanpa kunci, dan jalankan tool ini sebagai bacaan read only dengan pustaka standar Python saja.

- Uji otomatisnya berjumlah 37 tes dengan jaringan yang dimock dan sudah lolos, dan bacaan live pada MAGMA tanggal 12 November 2026 sudah memverifikasi bahwa sinyal 5m MELEMAH terbaca saat pullback, padahal candle 15m belum tutup.

- Jangan klaim estimator slippage, peringatan delta di bawah 60 detik, retry saat timeout atau 429, batas timestamp, filter likuiditas, level watcher, atau kalibrasi backtest, karena semuanya masih ditunda dan belum dibangun.

- Ingatkan user untuk memverifikasi harga di layarnya sendiri sebelum eksekusi, karena data live bisa tertunda beberapa detik.

## Available connectors

- Use `muse.connector_search` to find other connectors and `muse.skill_search` to find related skills.

- If nothing here fits, look on the web for a maintained API or MCP server and set it up with [Custom Connectors and MCPs](/opt/muse/skills/custom-connector-setup/SKILL.md), or build a custom connector.

## Alternatives for better results

- Pasangkan live confirm dengan `candle-reader-15m` untuk konfirmasi candle tutup dan dengan `entry-assistant` untuk angka entry, stop, dan target.

- Gunakan `trade-planner-spot` untuk mengubah level yang terkonfirmasi live menjadi rencana bersyarat dengan pemicu dan invalidasi.

- Bila live check gagal total, jalankan ketiga tool satu per satu, yaitu `reader_5m.py`, `orderbook.py`, dan `delta.py`, dengan file JSON dari endpoint publik Bitget.
