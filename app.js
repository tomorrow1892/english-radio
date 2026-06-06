// English Radio - Frontend Application
// Handles news fetching, TTS playback, and bilingual sync highlighting

class SpeechController {
  constructor(app) {
    this.app = app;
    this.isPlaying = false;
    this.isPaused = false;
  }

  get rate() {
    return parseFloat(this.app.elements.rangeRate.value);
  }

  get voice() {
    const name = this.app.elements.selectVoice.value;
    return this.app.voices.find((v) => v.name === name) || this.app.selectedVoice;
  }

  play() {
    if (!this.app.currentArticle?.sentences?.length) return;
    if (typeof speechSynthesis === 'undefined') return;

    if (this.isPaused && speechSynthesis.paused) {
      speechSynthesis.resume();
      this.isPaused = false;
      this.isPlaying = true;
      this.app.setPlayingState(true);
      this.app.updatePlayButton();
      return;
    }

    speechSynthesis.cancel();
    this.isPlaying = true;
    this.isPaused = false;
    this.app.setPlayingState(true);
    this.app.updatePlayButton();
    this.speakFromIndex(this.app.currentSentenceIndex);
  }

  pause() {
    if (!this.isPlaying || typeof speechSynthesis === 'undefined') return;
    speechSynthesis.pause();
    this.isPaused = true;
    this.isPlaying = false;
    this.app.setPlayingState(false);
    this.app.updatePlayButton();
  }

  stop() {
    if (typeof speechSynthesis === 'undefined') return;
    speechSynthesis.cancel();
    this.isPlaying = false;
    this.isPaused = false;
    this.app.setPlayingState(false);
    this.app.updatePlayButton();
  }

  speakFromIndex(index) {
    const sentences = this.app.currentArticle?.sentences;
    if (!sentences || index >= sentences.length) {
      this.onPlaybackComplete();
      return;
    }

    const utterance = new SpeechSynthesisUtterance(sentences[index].en);
    utterance.rate = this.rate;
    utterance.lang = 'en-US';
    if (this.voice) utterance.voice = this.voice;

    utterance.onstart = () => {
      this.app.highlightSentence(index);
    };

    utterance.onend = () => {
      if (this.isPlaying && index < sentences.length - 1) {
        this.speakFromIndex(index + 1);
      } else {
        this.onPlaybackComplete();
      }
    };

    utterance.onerror = (event) => {
      if (event.error !== 'canceled') {
        console.error('Speech synthesis error:', event.error);
      }
      this.onPlaybackComplete();
    };

    speechSynthesis.speak(utterance);
  }

  onPlaybackComplete() {
    this.isPlaying = false;
    this.isPaused = false;
    this.app.setPlayingState(false);
    this.app.updatePlayButton();
  }

  restartFromCurrentSentence() {
    if (!this.isPlaying && !this.isPaused) return;
    speechSynthesis.cancel();
    this.isPaused = false;
    this.isPlaying = true;
    this.app.setPlayingState(true);
    this.app.updatePlayButton();
    this.speakFromIndex(this.app.currentSentenceIndex);
  }
}

class EnglishRadioApp {
  constructor() {
    this.newsData = [];
    this.currentArticle = null;
    this.currentSentenceIndex = 0;
    this.voices = [];
    this.selectedVoice = null;
    this.speech = new SpeechController(this);

    this.elements = {
      appContainer: document.getElementById('app-container'),
      newsList: document.getElementById('news-list'),
      newsCount: document.getElementById('news-count'),
      activeHeader: document.getElementById('active-article-header'),
      btnBackToList: document.getElementById('btn-back-to-list'),
      playerCard: document.querySelector('.player-card'),
      btnPlay: document.getElementById('btn-play'),
      btnStop: document.getElementById('btn-stop'),
      btnPrev: document.getElementById('btn-prev'),
      btnNext: document.getElementById('btn-next'),
      selectVoice: document.getElementById('select-voice'),
      rangeRate: document.getElementById('range-rate'),
      rateValue: document.getElementById('rate-value'),
      summaryBox: document.getElementById('summary-box'),
      summaryText: document.getElementById('english-summary-text'),
      transcriptContainer: document.getElementById('transcript-container'),
      currentSentenceDisplay: document.getElementById('current-sentence-display'),
      currentEn: document.getElementById('current-en'),
      currentJa: document.getElementById('current-ja'),
    };

    this.init();
  }

  async init() {
    this.setupEventListeners();
    this.initVoices();
    await this.fetchNews();
    this.handleRoute();
  }

  setupEventListeners() {
    this.elements.btnPlay.addEventListener('click', () => this.togglePlayPause());
    this.elements.btnStop.addEventListener('click', () => this.stopPlayback());
    this.elements.btnPrev.addEventListener('click', () => this.goToPrevSentence());
    this.elements.btnNext.addEventListener('click', () => this.goToNextSentence());
    this.elements.btnBackToList.addEventListener('click', () => this.navigateToList());
    window.addEventListener('hashchange', () => this.handleRoute());

    this.elements.rangeRate.addEventListener('input', (e) => {
      const rate = parseFloat(e.target.value);
      this.elements.rateValue.textContent = `${rate.toFixed(1)}x`;
      if (this.speech.isPlaying) {
        this.speech.restartFromCurrentSentence();
      }
    });

    this.elements.selectVoice.addEventListener('change', (e) => {
      this.selectedVoice = this.voices.find((v) => v.name === e.target.value) || null;
      if (this.speech.isPlaying) {
        this.speech.restartFromCurrentSentence();
      }
    });
  }

  initVoices() {
    if (typeof speechSynthesis === 'undefined') {
      console.warn('Web Speech API is not supported in this browser.');
      return;
    }

    const loadVoices = () => {
      this.voices = speechSynthesis.getVoices().filter((v) => v.lang.startsWith('en'));

      if (this.voices.length > 0) {
        this.elements.selectVoice.innerHTML = this.voices
          .map((v) => `<option value="${v.name}">${v.name} (${v.lang})</option>`)
          .join('');
        this.elements.selectVoice.disabled = false;
        this.elements.rangeRate.disabled = false;
        this.selectedVoice = this.voices[0];
      } else {
        this.elements.selectVoice.innerHTML = '<option value="">No English Voice Available</option>';
      }
    };

    loadVoices();
    if (speechSynthesis.onvoiceschanged !== undefined) {
      speechSynthesis.onvoiceschanged = loadVoices;
    }
  }

  validateNewsItem(item) {
    return (
      item &&
      typeof item === 'object' &&
      Array.isArray(item.sentences) &&
      item.sentences.every((s) => s && typeof s.en === 'string' && typeof s.ja === 'string')
    );
  }

  async fetchNews() {
    try {
      const response = await fetch('data/news.json');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const data = await response.json();

      // Store structured data for category-based rendering
      this.newsDataStructured = {};
      this.newsData = [];

      if (data.main_news && Array.isArray(data.main_news)) {
        // New multi-category structure
        const mainNews = data.main_news.filter((item) => this.validateNewsItem(item));
        if (mainNews.length > 0) {
          this.newsDataStructured['主要ニュース'] = mainNews;
          this.newsData.push(...mainNews);
        }

        if (data.category_news && typeof data.category_news === 'object') {
          // Store category news with their labels
          Object.entries(data.category_news).forEach(([category, articles]) => {
            if (Array.isArray(articles)) {
              const validArticles = articles.filter((item) => this.validateNewsItem(item));
              if (validArticles.length > 0) {
                this.newsDataStructured[category] = validArticles;
                this.newsData.push(...validArticles);
              }
            }
          });
        }
      } else if (Array.isArray(data)) {
        // Legacy array format
        this.newsData = data.filter((item) => this.validateNewsItem(item));
        this.newsDataStructured = {}; // Empty for legacy format
      }

      this.renderNewsList();

      if (this.newsData.length > 0) {
        this.selectArticle(0);
      }
    } catch (error) {
      console.error('Failed to load news:', error);
      this.renderErrorState();
    }
  }

  renderNewsList() {
    if (this.newsData.length === 0) {
      this.elements.newsList.innerHTML = `
        <div class="loading-state">
          <p>配信中のニュースがありません。</p>
        </div>
      `;
      this.elements.newsCount.textContent = '0 件';
      return;
    }

    this.elements.newsCount.textContent = `${this.newsData.length} 件`;

    // If we have structured data, render with categories
    if (Object.keys(this.newsDataStructured).length > 0) {
      let html = '';

      Object.entries(this.newsDataStructured).forEach(([categoryLabel, articles]) => {
        html += `
          <div class="news-category-section">
            <div class="category-header">${categoryLabel}</div>
            <div class="category-cards">
              ${articles.map((article, catIndex) => {
          const globalIndex = this.newsData.indexOf(article);
          return `
                  <div class="news-card" data-index="${globalIndex}">
                    <div class="news-card-title">${article.title_ja || article.title}</div>
                    <div class="news-card-meta">
                      <span>${article.date || '今日'}</span>
                      <span>${article.sentences.length} 文</span>
                    </div>
                  </div>
                `;
        }).join('')}
            </div>
          </div>
        `;
      });

      this.elements.newsList.innerHTML = html;
    } else {
      // Legacy rendering (flat list)
      this.elements.newsList.innerHTML = this.newsData
        .map(
          (article, index) => `
          <div class="news-card" data-index="${index}">
            <div class="news-card-title">${article.title_ja || article.title}</div>
            <div class="news-card-meta">
              <span>${article.date || '今日'}</span>
              <span>${article.sentences.length} 文</span>
            </div>
          </div>
        `
        )
        .join('');
    }

    this.elements.newsList.querySelectorAll('.news-card').forEach((card) => {
      card.addEventListener('click', () => {
        const index = parseInt(card.getAttribute('data-index'), 10);
        window.location.hash = `#/article/${index}`;
      });
    });
  }

  handleRoute() {
    const hash = window.location.hash || '#/list';
    const match = hash.match(/^#\/article\/(\d+)$/);

    if (match && this.newsData.length > 0) {
      const index = parseInt(match[1], 10);
      if (!Number.isNaN(index) && index >= 0 && index < this.newsData.length) {
        this.showArticlePage(index);
        return;
      }
    }

    this.showListPage();
  }

  showListPage() {
    this.currentArticle = null;
    this.elements.appContainer.classList.remove('view-article');
    this.elements.appContainer.classList.add('view-list');
    this.elements.btnBackToList.style.display = 'none';
    this.renderNewsList();
  }

  showArticlePage(index) {
    this.elements.appContainer.classList.remove('view-list');
    this.elements.appContainer.classList.add('view-article');
    this.elements.btnBackToList.style.display = 'inline-flex';
    this.selectArticle(index);
    // window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  navigateToList() {
    window.location.hash = '#/list';
  }

  renderErrorState() {
    this.elements.newsList.innerHTML = `
      <div class="loading-state" style="color: #ef4444;">
        <i data-lucide="alert-triangle"></i>
        <p>ニュースの読み込みに失敗しました。</p>
      </div>
    `;
    lucide.createIcons();
  }

  selectArticle(index) {
    this.stopPlayback();

    this.elements.newsList.querySelectorAll('.news-card').forEach((c) => c.classList.remove('active'));

    const card = this.elements.newsList.querySelector(`.news-card[data-index="${index}"]`);
    if (card) card.classList.add('active');

    this.currentArticle = this.newsData[index];
    this.currentSentenceIndex = 0;
    this.renderActiveArticle();
  }

  renderActiveArticle() {
    if (!this.currentArticle) return;

    this.elements.activeHeader.innerHTML = `
      <div class="active-article-details">
        <h3>${this.currentArticle.title_ja || this.currentArticle.title}</h3>
        <div class="active-article-original">
          <span>元記事: NHK News</span>
          ${this.currentArticle.url
        ? `<a href="${this.currentArticle.url}" target="_blank" rel="noopener" class="original-link-btn">
            表示 <i data-lucide="external-link" style="width:12px;height:12px;"></i>
          </a>`
        : ''
      }
        </div>
      </div>
    `;
    lucide.createIcons();



    if (this.currentArticle.sentences?.length > 0) {
      this.elements.transcriptContainer.innerHTML = this.currentArticle.sentences
        .map(
          (sentence, idx) => `
          <div class="transcript-sentence" data-idx="${idx}">
            <div class="sentence-en">${sentence.en}</div>
            <div class="sentence-ja">${sentence.ja}</div>
          </div>
        `
        )
        .join('');

      this.elements.transcriptContainer.querySelectorAll('.transcript-sentence').forEach((sent) => {
        sent.addEventListener('click', () => {
          const idx = parseInt(sent.getAttribute('data-idx'), 10);
          this.jumpToSentence(idx);
        });
      });

      this.elements.btnPlay.disabled = false;
      this.elements.btnStop.disabled = false;
      this.elements.btnPrev.disabled = false;
      this.elements.btnNext.disabled = false;

      this.highlightSentence(0);
    } else {
      this.elements.transcriptContainer.innerHTML = `
        <div class="empty-transcript">
          <p>学習テキストデータがありません。</p>
        </div>
      `;
      this.clearCurrentSentenceDisplay();
    }
  }

  highlightSentence(index) {
    if (!this.currentArticle?.sentences?.length) return;

    this.currentSentenceIndex = index;
    const sentences = this.elements.transcriptContainer.querySelectorAll('.transcript-sentence');
    sentences.forEach((s, idx) => {
      if (idx === index) {
        s.classList.add('active');
        // s.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      } else {
        s.classList.remove('active');
      }
    });

    const current = this.currentArticle.sentences[index];
    if (current) {
      this.elements.currentEn.textContent = current.en;
      this.elements.currentJa.textContent = current.ja;
      this.elements.currentSentenceDisplay.classList.add('visible');
    }

    this.elements.btnPrev.disabled = index === 0;
    this.elements.btnNext.disabled = index === sentences.length - 1;
  }

  clearCurrentSentenceDisplay() {
    this.elements.currentEn.textContent = '';
    this.elements.currentJa.textContent = '';
    this.elements.currentSentenceDisplay.classList.remove('visible');
  }

  togglePlayPause() {
    if (this.speech.isPlaying) {
      this.speech.pause();
    } else {
      this.speech.play();
    }
  }

  stopPlayback() {
    this.speech.stop();
  }

  setPlayingState(playing) {
    this.elements.playerCard.classList.toggle('playing', playing);
  }

  updatePlayButton() {
    const icon = this.elements.btnPlay.querySelector('.btn-icon');
    if (!icon) return;

    if (this.speech.isPlaying) {
      icon.setAttribute('data-lucide', 'pause');
      this.elements.btnPlay.title = '一時停止';
    } else {
      icon.setAttribute('data-lucide', 'play');
      this.elements.btnPlay.title = '再生';
    }
    lucide.createIcons();
  }

  goToPrevSentence() {
    if (this.currentSentenceIndex <= 0) return;
    this.jumpToSentence(this.currentSentenceIndex - 1);
  }

  goToNextSentence() {
    const max = (this.currentArticle?.sentences?.length || 0) - 1;
    if (this.currentSentenceIndex >= max) return;
    this.jumpToSentence(this.currentSentenceIndex + 1);
  }

  jumpToSentence(index) {
    if (!this.currentArticle?.sentences) return;

    const wasPlaying = this.speech.isPlaying;
    if (wasPlaying || this.speech.isPaused) {
      speechSynthesis.cancel();
      this.speech.isPaused = false;
      this.highlightSentence(index);
      if (wasPlaying) {
        this.speech.isPlaying = true;
        this.setPlayingState(true);
        this.updatePlayButton();
        this.speech.speakFromIndex(index);
      } else {
        this.speech.stop();
      }
    } else {
      this.highlightSentence(index);
    }
  }
}

document.addEventListener('DOMContentLoaded', () => {
  window.app = new EnglishRadioApp();
});
