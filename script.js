document.addEventListener('DOMContentLoaded', () => {

    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const resultDiv = document.getElementById('result');
    window.saveResultsAsPng = saveResultsAsPng;
    function saveResultsAsPng(elementId) {
        const element = document.getElementById(elementId);
        if (!element) {
            alert(`エラー: ID "${elementId}" の要素が見つかりません。`);
            return;
        }

        // html2canvasを使って要素をキャプチャ
        html2canvas(element, { 
            scale: 2, // 高解像度でキャプチャ
            useCORS: true, // クロスオリジン画像を許可 (グラフ画像などに対応)
            // キャプチャ対象がグラフ（Canvas）である場合、Canvasをそのままキャプチャするオプション
            allowTaint: true, 
            ignoreElements: (element) => {
                // 保存ボタン自体は画像に含めない
                return element.tagName === 'BUTTON' && element.textContent === 'PNG保存';
            }
        }).then(canvas => {
            // キャプチャしたCanvasをPNGデータURLに変換
            const dataURL = canvas.toDataURL('image/png');
            
            // ダウンロード用のリンクを作成し、自動クリック
            const a = document.createElement('a');
            a.href = dataURL;
            a.download = `${elementId}_${new Date().toISOString().slice(0, 10)}.png`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        }).catch(err => {
            console.error('PNG保存中にエラーが発生しました:', err);
            alert(`PNG保存エラーが発生しました: ${err.message}`);
        });
    }

    //MLX評価の結果を表示する関数
    function displayMlxEvaluation(result) {
        const resultEl = document.createElement('div');
        resultEl.className = 'result-item';
        const uniqueId = `${result.analysis_type}`;
        resultEl.id = uniqueId;
        let html = `<h3>${result.title}</h3>`;
        if (result.status === 'error') {
            html += `<p style="color: red; font-weight: bold;">エラー: ${result.message}</p>`;
        } else {
            result.data.forEach(task_result => {
                html += `<h4>タスク: ${task_result.task}</h4>`;
                html += '<table>';
                html += '<thead><tr><th>指標</th><th>値</th></tr></thead>';
                html += '<tbody>';
                html += `<tr><td>有効データペア数</td><td>${task_result.count}</td></tr>`;
                const mae_str = formatMetric(task_result.mae);
                const rmse_str = formatMetric(task_result.rmse);
                html += `<tr><td>MAE (平均絶対誤差)</td><td>${mae_str}</td></tr>`;
                html += `<tr><td>RMSE (二乗平均平方根誤差)</td><td>${rmse_str}</td></tr>`;
                html += `<tr><td>BodyTemp 平均</td><td>${task_result.mean_body_temp?.toFixed(3) ?? 'N/A'}</td></tr>`;
                html += `<tr><td>Object_C 平均</td><td>${task_result.mean_object_c?.toFixed(3) ?? 'N/A'}</td></tr>`;
                html += `<tr><td>Ambient_C 平均</td><td>${task_result.mean_ambient_c?.toFixed(3) ?? 'N/A'}</td></tr>`;
                html += '</tbody></table>';
            });
        }
        html += `<div style="text-align: right; margin-top: 10px;">
                    <button onclick="saveResultsAsPng('${uniqueId}')">PNG保存</button>
                 </div>`;

        resultEl.innerHTML = html;
        resultDiv.appendChild(resultEl);
    }

    // ファイルプレビューの結果を表示する関数
    function displayFilePreview(result) {
        const resultEl = document.createElement('div');
        resultEl.className = 'result-item';
        let html = `<h3>ファイル内容の表示</h3>`;

        if (result.status === 'error' || !result.data) {
            html += `<p style="color: red; font-weight: bold;">エラー: ${result.message || 'データを表示できません'}</p>`;
        } else {
            result.data.forEach(file => { // result.data はファイルのリスト
                html += `<h4>${file.filename}</h4>`;
                
                if (file.sheets && Array.isArray(file.sheets)) {
                    file.sheets.forEach(sheet => {
                        if (sheet.sheet_name) {
                            const safeSheetName = String(sheet.sheet_name).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                            html += `<h5 style="margin:0.5em 0 0.2em 1.5em;">シート: ${safeSheetName}</h5>`;
                        }
                        html += '<ul>';
                        if (sheet.data && Array.isArray(sheet.data)) {
                            sheet.data.forEach(item => {
                                const safeItem = String(item).replace(/</g, "&lt;").replace(/>/g, "&gt;");
                                html += `<li>${safeItem}</li>`;
                            });
                        } else {
                            html += '<li>(データがありません)</li>';
                        }
                        html += '</ul>';
                    });
                }
            });
        }
        resultEl.innerHTML = html;
        resultDiv.appendChild(resultEl);
    }

    // 汎用エラーを表示する関数
    function displayError(result) {
        const resultEl = document.createElement('div');
        resultEl.className = 'result-item';
        let html = `<h3>エラー</h3>`;
        html += `<p style="color: red; font-weight: bold;">${result.message || '不明なエラーが発生しました'}</p>`;
        resultEl.innerHTML = html;
        resultDiv.appendChild(resultEl);
    }

    // MAE/RMSE の値に応じてスタイルを適用するヘルパー関数
    function formatMetric(value) {
        if (value === null) {
            return 'N/A (データなし)';
        }
        const numericValue = parseFloat(value);
        const text = numericValue.toFixed(4);
        if (numericValue <= 0.3) {
            return `<span style="color: green; font-weight: bold;">${text}</span>`;
        } else if (numericValue > 1.0) {
            return `<span style="color: red; font-weight: bold;">${text}</span>`;
        } else {
            return text; 
        }
    }

    function formatMaxMetric(value) {
        if (value === null) {
            return 'N/A (データなし)';
        }
        const numericValue = parseFloat(value);
        const text = numericValue.toFixed(4);

        // [修正] 5以下なら緑、それ以外は赤
        if (numericValue <= 5.0) {
            return `<span style="color: green; font-weight: bold;">${text}</span>`;
        } else {
            return `<span style="color: red; font-weight: bold;">${text}</span>`;
        }
    }

    function displayMaxEvaluation(result) {
        const resultEl = document.createElement('div');
        resultEl.className = 'result-item';
        const uniqueId = `result-${result.analysis_type}-${Date.now()}`;
        resultEl.id = uniqueId;
        let html = `<h3>${result.title}</h3>`;
        
        if (result.status === 'error') {
            html += `<p style="color: red; font-weight: bold;">エラー: ${result.message}</p>`;
            resultEl.innerHTML = html;
            resultDiv.appendChild(resultEl);
            return;
        } 
        
        // [修正] result.data (辞書のリスト) をループ処理
        result.data.forEach(task_result => {
            html += `<h4>タスク: ${task_result.task}</h4>`;

            const eval_vs_ecg = task_result.eval_1;
            const eval_vs_fin = task_result.eval_2;

            html += '<table>';
            html += '<thead>';
            html += '<tr>';
            html += '<th></th>'; // 角
            html += `<th>${eval_vs_ecg.device_name}</th>`;
            html += `<th>${eval_vs_fin.device_name}</th>`;
            html += '</tr>';
            html += '</thead>';
            html += '<tbody>';

            // --- 行1: 元データ ---
            html += '<tr>';
            html += '<td>元データ</td>';
                      
            // vsECG (元データ)
            if (eval_vs_ecg.error) {
                html += `<td style="color: orange;">${eval_vs_ecg.error} (N=${eval_vs_ecg.raw_count})</td>`;
            } else {
                html += `<td>MAE: ${formatMaxMetric(eval_vs_ecg.raw_mae)}<br>RMSE: ${formatMaxMetric(eval_vs_ecg.raw_rmse)}<br>(N=${eval_vs_ecg.raw_count})</td>`;
            }
            // vsPPG_fin (元データ)
            if (eval_vs_fin.error) {
                html += `<td style="color: orange;">${eval_vs_fin.error} (N=${eval_vs_fin.raw_count})</td>`;
            } else {
                html += `<td>MAE: ${formatMaxMetric(eval_vs_fin.raw_mae)}<br>RMSE: ${formatMaxMetric(eval_vs_fin.raw_rmse)}<br>(N=${eval_vs_fin.raw_count})</td>`;
            }
            html += '</tr>';

            // --- 行2: 1分平均 ---
            html += '<tr>';
            html += '<td>1分平均</td>';
                      
            // vsECG (1分平均)
            if (eval_vs_ecg.error || eval_vs_ecg.resampled_count === 0) {
                html += `<td style="color: orange;">${eval_vs_ecg.error || 'データなし'} (N=${eval_vs_ecg.resampled_count})</td>`;
            } else {
                html += `<td>MAE: ${formatMaxMetric(eval_vs_ecg.resampled_mae)}<br>RMSE: ${formatMaxMetric(eval_vs_ecg.resampled_rmse)}<br>(N=${eval_vs_ecg.resampled_count})</td>`;
            }
            // vsPPG_fin (1分平均)
            // resampled_count が 0 の場合もエラーとして扱う
            if (eval_vs_fin.error || eval_vs_fin.resampled_count === 0) {
                html += `<td style="color: orange;">${eval_vs_fin.error || 'データなし'} (N=${eval_vs_fin.resampled_count})</td>`;
            } else {
                html += `<td>MAE: ${formatMaxMetric(eval_vs_fin.resampled_mae)}<br>RMSE: ${formatMaxMetric(eval_vs_fin.resampled_rmse)}<br>(N=${eval_vs_fin.resampled_count})</td>`;
            }
            html += '</tr>';

            html += '</tbody></table>';
        });
        html += `<div style="text-align: right; margin-top: 10px;">
                        <button onclick="saveResultsAsPng('${uniqueId}')">PNG保存</button>
                     </div>`;
        
        resultEl.innerHTML = html;
        resultDiv.appendChild(resultEl);
    }

    // --- メインの submit イベントリスナー ---
    uploadForm.addEventListener('submit', async function(event) {
        event.preventDefault();

        const formData = new FormData();
        for (const file of fileInput.files) {
            formData.append('files', file);
        }

        // [修正] チェックされた項目をすべて取得
        const checkedBoxes = document.querySelectorAll('input[name="analysis_type"]:checked');

        // [修正] チェックボックスの検証
        if (checkedBoxes.length === 0) {
            alert('実行したい解析メニューにチェックを入れてください。');
            resultDiv.innerHTML = ''; // 「解析中」の表示をクリア
            return; // 処理を中断
        }
        
        // [修正] チェックされた value をすべて FormData に追加
        checkedBoxes.forEach(box => {
            // 'analysis_types[]' という名前にすることで、Flask側で配列(List)として受け取れる
            formData.append('analysis_types[]', box.value); 
        });

        resultDiv.innerHTML = '解析中...';

        try {
            const response = await fetch('http://127.0.0.1:5000/upload', {
                method: 'POST',
                body: formData
            });

            // [修正] バックエンドからは結果の *配列* が返ってくる
            const results = await response.json(); 
            resultDiv.innerHTML = ''; // 「解析中」をクリア

            // 結果の配列をループ処理
            results.forEach(result => {
                // analysis_type に応じて適切な表示関数を呼び出す
                switch (result.analysis_type) {
                    case 'mlx_evaluation':
                        displayMlxEvaluation(result);
                        break;
                    case 'max_evaluation':
                        displayMaxEvaluation(result);
                        break;
                    case 'show_files':
                        displayFilePreview(result);
                        break;
                    case 'mlx_reevaluation':
                        displayMlxEvaluation(result);
                        break;
                    default:
                        // 'status': 'error' の場合なども含む
                        displayError(result);
                        break;
                }
            });

        } catch (error) {
            resultDiv.innerHTML = `JSON解析エラー．サーバーの応答を確認してください: ${error}`;
            console.error('Error:', error);
        }
    });

});