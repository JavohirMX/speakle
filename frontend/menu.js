
// モーダルを開く
function openSettings() {
    document.getElementById('modalOverlay').style.display = 'block';
    document.getElementById('settingsModal').style.display = 'block';
  }
  
  // 入力を保存してモーダルを閉じ、画面に表示
  function closeAndShowResult() {
    const name = document.getElementById("nameInput").value.trim();
    const nationality = document.getElementById("nationalityInput").value;
    const language = document.getElementById("languageInput").value;
  
    if (name === "") {
      alert("名前を入力してください");
      return;
    }
  
    // localStorage に保存
    localStorage.setItem("name", name);
    localStorage.setItem("nationality", nationality);
    localStorage.setItem("language", language);
  
    // モーダル閉じる
    document.getElementById('modalOverlay').style.display = 'none';
    document.getElementById('settingsModal').style.display = 'none';
  
    // 出力
    updateOutput();
  }
  
  // localStorage から値を取得して出力欄に表示
  function updateOutput() {
    const name = localStorage.getItem("name") || "";
    const nationality = localStorage.getItem("nationality") || "";
    const language = localStorage.getItem("language") || "";
  
    document.getElementById("nameOutput").innerText = " " + name;
    document.getElementById("nationalityOutput").innerText = " " + nationality;
    document.getElementById("languageOutput").innerText = " " + language;
  }
  
  // ページ読み込み時に localStorage の内容を表示
  window.onload = function() {
    updateOutput();
  };