
            var srcPath = "D:\\ERP文件存储\\设计文件夹\\卓越鸟旗舰店\\2025-12-22\\卓越鸟旗舰店^Q搜索学习中消息华利锋又要重新绑定^2^打样^80克铜版纸不干胶^印刷,不覆膜,模切^85x130^20^铜版纸不干胶^3138456972718459752^SJ202512224860.ai";
            var cols = 3;
            var rows = 1;
            var margin = 30;
            var keepOriginalAtTopLeft = true;
            var names = ["卓越鸟旗舰店^Q搜索学习中消息华利锋又要重新绑定^2^打样^80克铜版纸不干胶^印刷,不覆膜,模切^85x130^20^铜版纸不干胶^3138456972718459752^SJ202512224860", "卓越鸟旗舰店^Q搜索学习中消息华利锋又要重新绑定^1^打样^80克铜版纸不干胶^印刷,不覆膜,模切^40x60^50^铜版纸不干胶^3138456972718459752^SJ20251222485W", "卓越鸟旗舰店^Q搜索学习中消息华利锋又要重新绑定^1^打样^80克铜版纸不干胶^印刷,不覆膜,模切^45x160^100^铜版纸不干胶^3138456972718459752^SJ20251222485R"]; // 来自 Python 的名称列表

            function main() {
                var f = new File(srcPath);
                if (!f.exists) {
                    alert("源文件不存在: " + srcPath);
                    return;
                }
                app.open(f);
                var doc = app.activeDocument;
                doc.documentColorSpace = DocumentColorSpace.CMYK
                if (doc.artboards.length < 1) {
                    alert("文档中没有画板。");
                    doc.close(SaveOptions.DONOTSAVECHANGES);
                    return;
                }

                var refArt = doc.artboards[0];
                var rect = refArt.artboardRect;
                var width = rect[2] - rect[0];
                var height = rect[1] - rect[3];
                var startLeft = rect[0];
                var startTop = rect[1];

                var created = 0;
                var totalBefore = doc.artboards.length;
                var nameIndex = 0;

                for (var r = 0; r < rows; r++) {
                    for (var c = 0; c < cols; c++) {
                        if (keepOriginalAtTopLeft && r === 0 && c === 0) {
                            // 改名第一个原始画板
                            if (nameIndex < names.length) {
                                doc.artboards[0].name = names[nameIndex++];
                            }
                            continue;
                        }
                        var left = startLeft + c * (width + margin);
                        var top = startTop - r * (height + margin);
                        var newRect = [left, top, left + width, top - height];
                        var newArtboard = doc.artboards.add(newRect);
                        if (nameIndex < names.length) {
                            newArtboard.name = names[nameIndex++];
                        } else {
                            newArtboard.name = "Artboard_" + (totalBefore + created + 1);
                        }
                        created++;
                    }
                }

                try { doc.save(); } catch(e) { $.writeln("保存出错：" + e); }
                //alert("完成：新增 " + created + " 个画板。总数：" + doc.artboards.length);
            }
            main();
            