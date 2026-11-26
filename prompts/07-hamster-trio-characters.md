# 햄스터 3형제 캐릭터 설정 + 이미지 생성 프롬프트

> 레퍼런스 무드: 폰으로 대충 찍은 듯한 실사 사진, 자연광, 집 안 일상 배경, 얼굴 클로즈업·셀카 구도, 짤용 여백.
> 이미지 생성 AI(ChatGPT 이미지, Gemini, Midjourney 등)에 그대로 복붙해서 사용. 프롬프트는 영어가 결과가 더 안정적임.

## 캐릭터

| 이름 | 색 | 품종 느낌 | 성격 | 고정 특징 (매번 넣기) |
|---|---|---|---|---|
| **쌀떡** | 흰색 | 펄 정글리안(윈터화이트) | 새침, 멍때림 장인 | pure white fluffy fur, tiny pink nose, shiny black bead eyes, pale pink ears, very round body |
| **호떡** | 갈색 | 골든 아기 햄스터 | 먹보, 볼 빵빵 | warm caramel-golden fur, cream white belly, dark eyes, pink nose, chubby stuffed cheeks |
| **콩떡** | 회색 | 블루/아구티 정글리안 | 겁쟁이, 막내 | soft blue-grey fur with a thin dark stripe down the back, white belly, tiny dark eyes |

공통: 세 마리 모두 **손바닥에 쏙 들어가는 크기(about 7cm)**, 동글동글.

## 공통 스타일 (모든 프롬프트 끝에 붙이기)
```
candid smartphone photo, natural window daylight, realistic fur texture, shallow depth of field, slightly soft focus background, everyday cozy home setting, warm and casual, not illustration, not 3D render, no text, 4:5 vertical
```

## 1단계: 캐릭터 기준 사진 먼저 만들기 (얼굴 고정용)
```
Three tiny hamsters sitting side by side on a light beige blanket, looking at the camera: left is a pure white fluffy pearl winter white dwarf hamster with tiny pink nose and black bead eyes, middle is a chubby warm caramel-golden baby hamster with cream belly and stuffed cheeks, right is a soft blue-grey dwarf hamster with a thin dark back stripe and white belly. Each hamster is palm-sized, round, cute. + [공통 스타일]
```
→ 마음에 드는 결과가 나오면 그 이미지를 **레퍼런스로 첨부**해서 아래 장면들을 만들기.
- ChatGPT/Gemini: 사진 첨부 + "이 세 햄스터와 똑같은 외모로" 한 줄 추가
- Midjourney: `--cref <이미지URL>` (또는 `--oref`) + 같은 `--seed` 유지

## 2단계: 장면 프롬프트 (짤·게시물용)

| # | 장면 | 프롬프트 (끝에 공통 스타일 붙이기) | 짤 문구 예시 |
|---|---|---|---|
| 1 | 쌀떡 셀카 | Extreme close-up of the white hamster leaning into the camera lens, nose slightly blurry, blanket and blurry monitor in background | "어 찍히는 중임?" |
| 2 | 호떡 볼 빵빵 | The golden hamster with super stuffed cheeks held gently in a human hand, surprised open mouth, cozy bedroom | "아무것도 안 먹었는데요" |
| 3 | 콩떡 이불 속 | The grey hamster peeking out from under a grey knit blanket and blue sheet on a sofa, sleepy face | "애기 자깨요" 스타일 말풍선 |
| 4 | 귤 들기 | The white hamster standing on its hind legs on a water bottle cap, holding a small mandarin orange over its head with both paws | "오늘 운동 끝" |
| 5 | 완두콩 침낭 | The grey hamster lying on its back inside a tiny green felt pea-pod sleeping bag, holding a piece of cabbage, in a human palm | "출근 안 함" |
| 6 | 손가락 하이파이브 | The golden hamster touching a human fingertip with its tiny paw on a plain white table | "계약 성사" |
| 7 | 창가 햇살 | The white hamster sitting on a cream duvet by a sunny window with a tree outside, reaching one paw toward the camera | "주인아 일어나" |
| 8 | 셋이 간식 | All three hamsters around a single sunflower seed on a wooden desk, golden one reaching first | "싸우지 말고 나눠 먹어" |
| 9 | 밀짚모자 | The white hamster wearing a tiny straw hat on a car dashboard, blue sky through the windshield | "드라이브 가자" |
| 10 | 셋이 꾹 | Three hamsters squished together sleeping in a small ceramic cup on a kitchen counter, morning light | "오늘은 쉬는 날" |

## 팁
- 얼굴이 자꾸 바뀌면: 기준 사진을 매번 첨부 + "same hamster, same fur color and markings" 추가
- 너무 그림 같으면: `shot on iPhone, unedited, slight motion blur` 추가
- 사람 손이 이상하면: 손 없는 구도로 바꾸거나 `realistic human hand, five fingers` 추가
- X에 올릴 때는 AI 생성 이미지라고 표시해두는 게 좋음 (플랫폼 정책·신뢰도)
