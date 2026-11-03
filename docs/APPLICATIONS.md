# Первое приложение (P1)

Нативные приложения собираются **symbian-platform** (SymPort — тонкая обёртка с проверками профиля E52).
Часть цепочки **выполнена на реальном SDK** (`symbian-platform` 0.3.0): `symbian build` для ARMv5T, `package`,
инспекторы E32/SIS. Остальное (нативный SDK, `app init`, GUI) описано по документации и проверено только на
поддельном `symbian`.

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

## Что выполнено на реальном SDK

```bash
tools/sdk/verify-real-sdk.sh                # клонирует SDK (read-only), собирает пробный E32 и прогоняет SymPort
# вручную:
symport app build --project ~/e32_probe --mode toolchain --compiler ~/toolbin/clang++ --linker ~/toolbin/ld.lld
symport app package --project ~/e32_probe
symport app analyze ~/e32_probe --cross-check      # сверка разбора E32 с `symbian inspect`
symport sis inspect ~/e32_probe/.symbian/package/probe.sis
```

`--mode toolchain` вызывает низкоуровневый `symbian build` (только хостовые Clang/LLD, без нативного SDK): годится
для freestanding-проектов SDK вроде `probes/e32_probe`, но не для GUI-приложений с libc++/Window Server.

**Подводный камень Ninja.** SDK ищет `ninja` *рядом с компилятором* раньше, чем в `PATH`; системный Ninja 1.11
(`/usr/bin/ninja`) затеняет новый и сборка падает с `FAILED_PRECONDITION: ... Ninja 1.12 or later`. Решение — каталог с
симлинками на `clang++`, `ld.lld`, `cmake` и `ninja ≥ 1.12` (`pip install ninja`), путь к которому передаётся в
`--compiler/--linker` (скрипт выше делает это сам). `symport doctor` предупреждает об этом, а отчёты подсказывают решение.

## Критерии готовности P1 и фактическое состояние

| Критерий | Состояние |
|---|---|
| Создаётся минимальный native-проект | через `symbian init`; **не выполнено** (нужен нативный SDK, его нет в среде) |
| Сборка настоящим установленным SDK | **выполнено частично**: реальный `symbian build` собрал ARMv5T E32 (freestanding-проба); GUI/нативный SDK — нет |
| E32 анализируется | **выполнено** (разбор заголовка совпал с инспектором SDK на реальном образе, 15 полей; импорты — только синтетические образы) |
| SIS для поддерживаемого типа приложения | **выполнено**: реальный `symbian package` → SIS перечитан и совпал с инспектором SDK |
| Понятный отчёт зависимостей | **выполнено** (`app analyze`) |
| Непроверенные API не считаются совместимыми | **выполнено**: без firmware-профиля импорты `unknown` |

Для проверки на практике: установить SDK по `docs/INSTALL.md`, выполнить цепочку выше и приложить JSON-отчёты.
