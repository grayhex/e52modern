# Первое приложение (P1)

Нативные приложения собираются **symbian-platform** (SymPort — тонкая обёртка с проверками профиля E52).
Эти шаги описаны по документации SDK; **реальный SDK в среде разработки SymPort не запускался**, адаптер
проверен только на поддельном `symbian`.

```bash
symport doctor                                   # убедиться, что symbian найден
symport app init --name hello --target nokia-e52 --dest ~/dev/hello
symport app build --project ~/dev/hello
symport app inspect --project ~/dev/hello
symport app analyze ~/dev/hello --target nokia-e52
symport app package --project ~/dev/hello
symport sis inspect ~/dev/hello/.symbian/package/hello.sis
```

* `app init` вызывает `symbian init <dir> --name <name> --non-interactive --architecture armv5t`
  (профиль E52: целевой ABI ARMv5; по умолчанию SDK берёт ARMv6). Стартовый шаблон SDK — Window Server
  GUI-приложение (touch + Enter/Backspace/Clear), реальная работа клавиатуры на E52 не проверена.
  Тест-UID предлагаются в диапазоне `0xE…`; для публикации выдайте собственные.
* `app build` перед вызовом SDK проверяет, что в `symbian.toml` указана архитектура `armv5t`, и после сборки
  требует наличия `.symbian/build/<name>.exe`: «сборка без артефакта» — это ошибка.
* `app package` использует SIS-писатель SDK: только E32-исполняемые файлы, без DLL/зависимостей/скриптов.
  Результат перечитывается `symport.sis.reader`.
* Устанавливаемые приложения должны иметь UID пакета, отличный от UID3 исполняемого файла (проверяется).

## Критерии готовности P1 и фактическое состояние

| Критерий | Состояние |
|---|---|
| Создаётся минимальный native-проект | через `symbian init`; **не выполнено в этой среде** (нет SDK) |
| Сборка настоящим установленным SDK | **не выполнено в этой среде** |
| E32 анализируется | **выполнено** (собственный разбор заголовка/импортов + автотесты на синтетических образах) |
| SIS для поддерживаемого типа приложения | через SDK; перечитывание SIS — автотесты |
| Понятный отчёт зависимостей | **выполнено** (`app analyze`) |
| Непроверенные API не считаются совместимыми | **выполнено**: без firmware-профиля импорты `unknown` |

Для проверки на практике: установить SDK по `docs/INSTALL.md`, выполнить цепочку выше и приложить JSON-отчёты.
