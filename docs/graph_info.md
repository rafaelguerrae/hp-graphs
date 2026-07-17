# graph_info

## Fonte dos dados

O projeto usa exclusivamente o **HP Dialogue Dataset (HPD)**, produzido por pesquisadores da Peking University e disponível em [nuochenpku.github.io/HPD.github.io](https://nuochenpku.github.io/HPD.github.io/).

O dataset contém **sessões de diálogo** extraídas dos 7 livros de Harry Potter. Cada sessão registra:

- A lista de personagens que falam naquela cena
- O livro de origem (usado para filtrar por período: primeiros livros, meio, final)
- Os dados relacionais de cada personagem **na perspectiva do Harry**:
  - `affection` (afeição): o quanto Harry e o personagem se afeiçoam mutuamente, numa escala de -10 a 10
  - `familiarity` (familiaridade): o quanto se conhecem, numa escala de 0 a 10
  - O tipo dominante de relação binária: `friend`, `enemy`, `family`, `teacher`, `opponent`, etc.

> **Importante:** os dados relacionais (afeição, familiaridade, tipo de relação) existem **apenas para personagens que aparecem em cenas com o Harry**. Relações entre personagens secundários entre si não têm esses metadados.

## O que são os nós

Cada **nó** representa um personagem. Seus atributos são:

| Atributo | Descrição |
|---|---|
| `appearances` | Total de sessões em que o personagem aparece |
| `affection` | Média de afeição com o Harry ao longo das sessões (apenas personagens de Harry) |
| `familiarity` | Média de familiaridade com o Harry (apenas personagens de Harry) |
| `relation_type` | Tipo de relação dominante com o Harry |

O tamanho visual do nó no grafo é proporcional ao número de aparições (escala logarítmica).

## O que são as arestas e como são criadas

Uma **aresta** conecta dois personagens que aparecem juntos em pelo menos uma mesma sessão de diálogo. Isso é chamado de **co-ocorrência**.

Para cada sessão, o código gera todos os pares possíveis de personagens presentes e incrementa um contador:

```
Sessão com [Harry, Hermione, Ron]
→ pares gerados: Harry↔Hermione, Harry↔Ron, Hermione↔Ron
```

Existe um filtro `min_cooccur` (padrão: 2) que descarta arestas com poucas co-ocorrências, eliminando conexões superficiais.

As arestas são **não-dirigidas**: a conexão entre A e B é a mesma que entre B e A, sem sentido preferencial.

## Como o peso da aresta é calculado

O peso representa a **força da conexão** entre dois personagens. É calculado pela fórmula:

```
weight = log(co_occurrences + 1) × (1 + bonus)
```

### Componente base

```
base = log(co_ocorrências + 1)
```

Usa logaritmo para suavizar a escala: personagens que dividem 100 cenas não ficam 10x mais importantes do que os que dividem 10.

### Componente bonus (só para arestas com Harry)

Como os dados emocionais existem apenas para o Harry, o bonus só é aplicado em arestas do tipo `Harry ↔ X`:

```
norm_aff = (affection + 10) / 20   → normaliza -10..10 para 0..1
norm_fam = familiarity / 10        → normaliza 0..10 para 0..1
bonus    = (norm_aff + norm_fam) / 2
```

Os valores de `affection` e `familiarity` usados aqui são **médias bilaterais**: a média entre o que Harry sente pelo personagem e o que o personagem sente pelo Harry, calculada ao longo de todas as sessões.

### Efeito prático

| Relação | Co-ocorrências | Afeição | Peso resultante |
|---|---|---|---|
| Harry ↔ Hermione | alto | alta | muito alto |
| Harry ↔ Draco | alto | negativa | moderado (bonus penaliza) |
| Hermione ↔ Ron | alto | — | alto (só base, sem bonus) |

## Direção do grafo

O grafo é **não-dirigido**. Embora o dataset original registre a perspectiva dos dois lados (o que Harry sente pelo personagem e o que o personagem sente pelo Harry), o projeto **simetriza** esses valores calculando a média bilateral. O objetivo é capturar a *intensidade* da relação, não sua assimetria.